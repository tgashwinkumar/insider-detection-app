import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.utils.constants import ALERTS_CHANNEL

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    await manager.connect(websocket)
    redis_task = asyncio.create_task(_redis_listener(websocket))
    try:
        while True:
            # Keep connection alive by awaiting messages (client may send pings)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send a ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        redis_task.cancel()
        manager.disconnect(websocket)


async def _redis_listener(websocket: WebSocket) -> None:
    """Subscribe to Redis pub/sub and forward messages to this WebSocket client."""
    try:
        from app.redis_client import get_redis
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(ALERTS_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception as e:
                    logger.warning(f"Failed to forward alert: {e}")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Redis listener error: {e}")


@router.websocket("/ws/market/{condition_id}")
async def websocket_market(websocket: WebSocket, condition_id: str):
    """
    Per-market WebSocket endpoint.
    Frontend connects when MarketDetailPage mounts for a given conditionId.

    On connect:
      - Looks up the market's token IDs from MongoDB
      - Tells PolymarketSubscriptionManager to subscribe those tokens
      - Subscribes to Redis channel sentinel:live:{condition_id}
      - Forwards Redis messages (trade_pending / new_trade) to the client

    On disconnect:
      - Tells manager to unsubscribe (ref-counted; actual Polymarket WS
        unsubscription only happens when the last viewer leaves)
    """
    await websocket.accept()

    from app.models.market import Market
    from app.redis_client import get_redis
    from app.services.indexer.polymarket_live_listener import subscription_manager

    # Fetch token IDs stored during backfill ingestion
    market = await Market.find_one(Market.condition_id == condition_id)
    token_ids: list[str] = (market.token_ids if market else []) or []

    await subscription_manager.subscribe(condition_id, token_ids)

    redis = get_redis()
    pubsub = redis.pubsub()
    channel = f"sentinel:live:{condition_id}"
    await pubsub.subscribe(channel)

    redis_task = asyncio.create_task(_market_redis_listener(websocket, pubsub))
    logger.info(f"Market WS connected: {condition_id} (tokens={len(token_ids)})")

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"Market WS error ({condition_id}): {e}")
    finally:
        redis_task.cancel()
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        await subscription_manager.unsubscribe(condition_id)
        logger.info(f"Market WS disconnected: {condition_id}")


async def _market_redis_listener(websocket: WebSocket, pubsub) -> None:
    """Forward per-market Redis pub/sub messages to a single WebSocket client."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception as e:
                    logger.warning(f"Failed to forward market update: {e}")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Market Redis listener error: {e}")
