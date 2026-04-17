"""
Polymarket CLOB WebSocket live listener.

Subscribes to the Polymarket Market Channel per market (using token IDs).
Only markets currently viewed in the frontend are subscribed — the backend
/ws/market/{condition_id} endpoint calls subscribe/unsubscribe to manage this.

Flow for each last_trade_price event:
  1. Publish trade_pending to Redis sentinel:live:{condition_id}
     → forwarded to the frontend immediately (pulsing placeholder row)
  2. After 45s delay (blockchain + subgraph indexing time):
     → Query subgraph for new trades on that asset_id since the event timestamp
     → Dispatch live_score_task for each trade found (gives maker/taker/tx_hash)
     → live_score_task publishes new_trade to Redis after scoring
"""
import asyncio
import json
import logging
from typing import Optional

import websockets

logger = logging.getLogger(__name__)

POLYMARKET_MARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
RECONCILE_DELAY_SECONDS = 45
PING_INTERVAL_SECONDS = 10


class PolymarketSubscriptionManager:
    """
    Singleton that maintains one persistent WebSocket connection to Polymarket's
    Market Channel and manages per-market subscriptions by token ID.
    """

    def __init__(self) -> None:
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._task: Optional[asyncio.Task] = None
        # condition_id → list of token_ids
        self._condition_tokens: dict[str, list[str]] = {}
        # token_id → condition_id (reverse lookup for routing events)
        self._token_to_condition: dict[str, str] = {}
        # condition_id → viewer count (ref counting for auto-unsubscribe)
        self._viewer_counts: dict[str, int] = {}
        self._lock = asyncio.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background WebSocket loop. Called on app startup."""
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())
        logger.info("PolymarketSubscriptionManager started")

    async def stop(self) -> None:
        """Cancel the background task. Called on app shutdown."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PolymarketSubscriptionManager stopped")

    # ── Public API — called by /ws/market/{condition_id} endpoint ─────────────

    async def subscribe(self, condition_id: str, token_ids: list[str]) -> None:
        """Register a frontend viewer for this market. Sends updated subscription to Polymarket."""
        async with self._lock:
            self._viewer_counts[condition_id] = self._viewer_counts.get(condition_id, 0) + 1
            if condition_id not in self._condition_tokens and token_ids:
                self._condition_tokens[condition_id] = token_ids
                for tid in token_ids:
                    self._token_to_condition[tid] = condition_id
                logger.info(
                    f"Subscribed to market {condition_id} "
                    f"({len(token_ids)} tokens, viewers={self._viewer_counts[condition_id]})"
                )
                await self._send_subscription()

    async def unsubscribe(self, condition_id: str) -> None:
        """Deregister a frontend viewer. Removes subscription when last viewer leaves."""
        async with self._lock:
            count = self._viewer_counts.get(condition_id, 0)
            if count <= 1:
                self._viewer_counts.pop(condition_id, None)
                tokens = self._condition_tokens.pop(condition_id, [])
                for tid in tokens:
                    self._token_to_condition.pop(tid, None)
                logger.info(f"Unsubscribed from market {condition_id} (no more viewers)")
                await self._send_subscription()
            else:
                self._viewer_counts[condition_id] = count - 1
                logger.debug(
                    f"Viewer left {condition_id}, remaining={self._viewer_counts[condition_id]}"
                )

    # ── Internal WebSocket loop ────────────────────────────────────────────────

    async def _run(self) -> None:
        """Persistent reconnecting loop. Runs for the lifetime of the app."""
        while True:
            try:
                async with websockets.connect(
                    POLYMARKET_MARKET_WS_URL,
                    ping_interval=None,  # we handle pings manually
                    close_timeout=5,
                    open_timeout=10,
                ) as ws:
                    self._ws = ws
                    logger.info("Connected to Polymarket Market Channel WebSocket")

                    # Re-send subscription for any currently active markets
                    # (important after reconnect)
                    await self._send_subscription()

                    ping_task = asyncio.create_task(self._ping_loop(ws))
                    try:
                        async for raw in ws:
                            await self._handle_raw_message(raw)
                    finally:
                        ping_task.cancel()
                        self._ws = None

            except asyncio.CancelledError:
                logger.info("Polymarket WS loop cancelled")
                return
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Polymarket WS connection closed, reconnecting in 5s...")
                self._ws = None
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Polymarket WS error: {e}, reconnecting in 10s...")
                self._ws = None
                await asyncio.sleep(10)

    async def _ping_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        """Send PING every 10 seconds as required by Polymarket's heartbeat protocol."""
        try:
            while True:
                await asyncio.sleep(PING_INTERVAL_SECONDS)
                try:
                    await ws.send("PING")
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def _send_subscription(self) -> None:
        """
        Send the current full token list as a subscription message.
        Called after subscribe/unsubscribe and on reconnect.
        If not yet connected, schedules a retry for when the connection opens.
        """
        all_tokens = list(self._token_to_condition.keys())
        if not all_tokens:
            logger.debug("_send_subscription: no tokens registered, skipping")
            return
        if not self._ws:
            logger.info(
                f"_send_subscription: Polymarket WS not connected yet — "
                f"subscription for {len(all_tokens)} tokens will be sent on connect"
            )
            return
        try:
            msg = json.dumps({
                "assets_ids": all_tokens,
                "type": "market",
                "custom_feature_enabled": True,
            })
            await self._ws.send(msg)
            logger.info(
                f"Sent Polymarket subscription with {len(all_tokens)} tokens: {all_tokens}"
            )
        except Exception as e:
            logger.warning(f"Failed to send subscription: {e}")

    # ── Message handling ───────────────────────────────────────────────────────

    async def _handle_raw_message(self, raw: str | bytes) -> None:
        if raw == "PONG" or raw == b"PONG":
            logger.debug("Polymarket WS: received PONG")
            return
        try:
            msg = json.loads(raw)
        except Exception:
            logger.debug(f"Polymarket WS: non-JSON message: {str(raw)[:100]}")
            return

        # Log every event type received so we can see what Polymarket is sending
        if isinstance(msg, list):
            types = {item.get("event_type") for item in msg if isinstance(item, dict)}
            logger.info(f"Polymarket WS: received batch of {len(msg)} messages, types={types}")
            for item in msg:
                if isinstance(item, dict) and item.get("event_type") == "last_trade_price":
                    await self._handle_trade_event(item)
        elif isinstance(msg, dict):
            event_type = msg.get("event_type", "unknown")
            if event_type == "last_trade_price":
                await self._handle_trade_event(msg)
            else:
                logger.info(f"Polymarket WS: received event_type={event_type}")

    async def _handle_trade_event(self, event: dict) -> None:
        """
        Handle a last_trade_price event from Polymarket.
        Publishes a pending signal immediately, then schedules reconciliation.
        """
        asset_id = event.get("asset_id", "")
        # The `market` field is the condition_id; fall back to our lookup table
        condition_id = event.get("market", "") or self._token_to_condition.get(asset_id, "")
        price = event.get("price", "0")
        side = event.get("side", "BUY")
        size = event.get("size", "0")

        try:
            timestamp = int(float(event.get("timestamp", "0")))
        except (ValueError, TypeError):
            import time
            timestamp = int(time.time())

        if not condition_id:
            logger.debug(f"Received last_trade_price for unknown asset {asset_id}, ignoring")
            return

        logger.info(
            f"Live trade event: market={condition_id} asset={asset_id} "
            f"side={side} price={price} size={size}"
        )

        # Phase 1: publish trade_pending immediately so frontend can show placeholder
        try:
            from app.redis_client import get_redis
            redis = get_redis()
            pending = json.dumps({
                "type": "trade_pending",
                "conditionId": condition_id,
                "asset_id": asset_id,
                "price": price,
                "side": side,
                "size": size,
                "timestamp": timestamp,
            })
            await redis.publish(f"sentinel:live:{condition_id}", pending)
        except Exception as e:
            logger.warning(f"Failed to publish trade_pending: {e}")

        # Phase 2: schedule reconciliation after subgraph indexing delay
        asyncio.create_task(
            self._reconcile_after_delay(asset_id, condition_id, timestamp)
        )

    async def _reconcile_after_delay(
        self,
        asset_id: str,
        condition_id: str,
        event_ts: int,
        delay: int = RECONCILE_DELAY_SECONDS,
    ) -> None:
        """
        After waiting for blockchain + subgraph indexing, query for new on-chain trades
        and dispatch them to live_score_task.
        """
        await asyncio.sleep(delay)
        try:
            from app.services.indexer.subgraph import subgraph_indexer
            from app.services.indexer.backfill import _parse_event_to_trade

            # Use a small buffer below the event timestamp to avoid missing the trade
            after_ts = max(0, event_ts - 30)
            events = await subgraph_indexer.fetch_recent_events_by_asset(
                asset_ids=[asset_id],
                after_ts=after_ts,
            )

            if not events:
                logger.info(
                    f"Reconciliation found no on-chain trades for asset={asset_id} "
                    f"after ts={after_ts}. Trade may not be indexed yet."
                )
                return

            dispatched = 0
            for event in events:
                trade_data = _parse_event_to_trade(event, condition_id)
                tx_hash = trade_data.get("transaction_hash", "")
                if not tx_hash:
                    continue
                try:
                    from app.tasks.live_score import live_score_task
                    live_score_task.apply_async(args=[trade_data])
                    dispatched += 1
                except Exception as e:
                    logger.warning(f"Could not enqueue live_score task for {tx_hash}: {e}")

            logger.info(
                f"Reconciliation dispatched {dispatched} live_score tasks "
                f"for market={condition_id}"
            )

        except Exception as e:
            logger.error(f"Reconciliation failed for asset={asset_id}: {e}")


# Singleton used by ws.py and main.py
subscription_manager = PolymarketSubscriptionManager()
