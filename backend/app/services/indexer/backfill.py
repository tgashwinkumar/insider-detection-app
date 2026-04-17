"""
Backfill orchestrator: coordinates the full historical ingestion pipeline.

Flow:
  resolve query → upsert Market → resolve token IDs (subgraph + Gamma fallback)
  → stream OrderFilled batches from The Graph → upsert Trades → update Redis job state
  → create Wallet stubs → enrich deposits → score all trades → update Market verdict
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.models.trade import Trade
from app.models.wallet import Wallet
from app.models.market import Market
from app.services.market_service import market_service
from app.services.indexer.subgraph import subgraph_indexer
from app.services.indexer import ingest_job

logger = logging.getLogger(__name__)

NULL_ADDRESS = "0x0000000000000000000000000000000000000000"


def _determine_direction(event: dict, yes_token_id: str = "", no_token_id: str = "") -> str:
    """
    Determine YES/NO direction from the event's asset IDs.

    Polymarket order fills have two roles:
      BUY  — maker offers collateral (USDC), taker receives outcome token
             takerAssetId = YES or NO token ID
      SELL — maker offers outcome token, taker receives collateral ("0" for NegRisk)
             makerAssetId = YES or NO token ID

    Priority:
      1. Exact match against known yes/no token IDs (takerAssetId first, then makerAssetId)
      2. Heuristic: use takerAssetId unless it is "0" (collateral), then use makerAssetId
         Even integer token ID → YES (outcomeIndex 0), odd → NO (outcomeIndex 1)
    """
    taker_asset = str(event.get("takerAssetId", ""))
    maker_asset = str(event.get("makerAssetId", ""))

    # Exact match — taker side (BUY orders)
    if yes_token_id and taker_asset == yes_token_id:
        return "yes"
    if no_token_id and taker_asset == no_token_id:
        return "no"

    # Exact match — maker side (SELL orders)
    if yes_token_id and maker_asset == yes_token_id:
        return "yes"
    if no_token_id and maker_asset == no_token_id:
        return "no"

    # Heuristic: "0" means collateral (NegRisk SELL), so inspect makerAssetId instead
    asset_to_check = maker_asset if taker_asset == "0" else taker_asset
    try:
        val = int(asset_to_check)
        return "yes" if val % 2 == 0 else "no"
    except (ValueError, TypeError):
        return "yes"


def _usdc_amount(
    maker_asset_id: str,
    taker_asset_id: str,
    maker_amount: float,
    taker_amount: float,
) -> float:
    """
    Return the USDC value of a fill in human-readable dollars.

    In every OrderFilled event exactly one asset is USDC (asset ID "0");
    the other is an outcome token. Both are stored as integers scaled by 1e6.

      takerAssetId == "0"  →  taker provides USDC  →  takerAmountFilled / 1e6
      makerAssetId == "0"  →  maker provides USDC  →  makerAmountFilled / 1e6

    The previous code always used takerAmountFilled / 1e6, which is wrong for
    SELL orders where the maker provides USDC. Those fills returned the
    outcome-token amount (in token units) as the dollar value, producing
    numbers that can be off by thousands of times.
    """
    if str(taker_asset_id) == "0":
        return taker_amount / 1e6
    if str(maker_asset_id) == "0":
        return maker_amount / 1e6
    # Neither side is collateral — shouldn't occur in normal fills.
    # Fall back to the smaller value as a conservative estimate.
    return min(maker_amount, taker_amount) / 1e6


def _parse_event_to_trade(
    event: dict,
    condition_id: str,
    yes_token_id: str = "",
    no_token_id: str = "",
) -> dict:
    ts = int(event.get("blockTimestamp") or event.get("timestamp") or 0)
    maker_amount = float(event.get("makerAmountFilled", 0))
    taker_amount = float(event.get("takerAmountFilled", 0))
    fee = float(event.get("fee", 0))
    maker_asset_id = str(event.get("makerAssetId", ""))
    taker_asset_id = str(event.get("takerAssetId", ""))
    amount_usdc = _usdc_amount(maker_asset_id, taker_asset_id, maker_amount, taker_amount)

    return {
        "transaction_hash": event.get("transactionHash") or event.get("id", ""),
        "block_number": int(event.get("blockNumber", 0)),
        "timestamp": ts,
        "maker": (event.get("maker") or "").lower(),
        "taker": (event.get("taker") or "").lower(),
        "maker_asset_id": maker_asset_id,
        "taker_asset_id": taker_asset_id,
        "maker_amount_filled": maker_amount,
        "taker_amount_filled": taker_amount,
        "fee": fee,
        "amount_usdc": amount_usdc,
        "direction": _determine_direction(event, yes_token_id, no_token_id),
        "condition_id": condition_id,
        "source": "historical",
    }


class BackfillOrchestrator:

    async def ingest_market(self, condition_id: str) -> None:
        """
        Full ingestion pipeline for a market, with Redis job state tracking.
        Idempotent: skips if a job is already running or done.
        """
        # Guard: don't start duplicate ingestion
        if await ingest_job.is_job_running(condition_id):
            logger.info(f"Skipping ingest for {condition_id}: job already running")
            return

        # Acquire lock (prevents race condition on concurrent requests)
        if not await ingest_job.acquire_lock(condition_id):
            logger.info(f"Could not acquire lock for {condition_id}, another process is starting it")
            return

        try:
            await self._run_ingestion(condition_id)
        except Exception as e:
            logger.exception(f"Ingestion failed for {condition_id}: {e}")
            await ingest_job.fail_job(condition_id, str(e))
        finally:
            await ingest_job.release_lock(condition_id)

    async def _run_ingestion(self, condition_id: str) -> None:
        logger.info(f"Starting ingestion for market {condition_id}")
        await ingest_job.create_job(condition_id)

        # ── Step 1: Resolve market metadata ────────────────────────────────────
        market = await self._resolve_market(condition_id)
        if not market:
            raise ValueError(f"Market {condition_id} not found in Gamma API or DB")

        # ── Step 2: Resolve YES/NO token IDs ──────────────────────────────────
        # Try both sources in parallel: Gamma API is the authoritative source for
        # clobTokenIds; the Orderbook subgraph also provides them with outcomeIndex
        # for YES/NO labelling. Gamma API is tried first because the subgraph can
        # time out intermittently, which previously caused the condition_id to be
        # used as the token ID (returning 0 trades).
        gamma_ids, token_map = await asyncio.gather(
            market_service.get_market_token_ids(condition_id),
            subgraph_indexer.resolve_token_ids_from_subgraph(condition_id),
            return_exceptions=True,
        )

        # Unpack safely — either call may have returned an Exception
        if isinstance(gamma_ids, Exception) or not isinstance(gamma_ids, list):
            gamma_ids = []
        if isinstance(token_map, Exception) or not isinstance(token_map, dict):
            token_map = {}

        yes_token = token_map.get("yes", "")
        no_token = token_map.get("no", "")
        subgraph_ids: list[str] = token_map.get("all", [])

        # Prefer Gamma API ids (always a complete, ordered list); use subgraph as
        # supplement if Gamma returned nothing.
        all_token_ids: list[str] = gamma_ids or subgraph_ids

        if not all_token_ids:
            logger.warning(f"No token IDs found for {condition_id}, using condition_id as fallback")
            all_token_ids = [condition_id]

        # If the subgraph didn't give YES/NO labels (e.g. NegRisk markets have
        # outcomeIndex=null), infer them from the Gamma API ordering:
        # clobTokenIds[i] corresponds to market.outcomes[i] ("Yes"/"No").
        if not yes_token and not no_token and len(gamma_ids) >= 2:
            market_outcomes: list[str] = getattr(market, "outcomes", []) or []
            for i, label in enumerate(market_outcomes):
                if i >= len(gamma_ids):
                    break
                if str(label).lower() in ("yes", "true"):
                    yes_token = gamma_ids[i]
                elif str(label).lower() in ("no", "false"):
                    no_token = gamma_ids[i]

        logger.info(f"Token IDs for {condition_id}: {all_token_ids} (yes={yes_token or 'unknown'}, no={no_token or 'unknown'})")

        # ── Step 3: Stream OrderFilled events from The Graph ───────────────────
        # Trades are scored incrementally: after each batch is upserted, new
        # wallets are enriched (deposit history + stats) and the batch's trades
        # are scored immediately. This means scored results are visible to the
        # frontend while later batches are still being fetched.
        trade_count = 0
        scored_count = 0
        wallet_addresses: set[str] = set()
        enriched_wallets: set[str] = set()  # avoid re-enriching across batches
        batches_processed = 0
        last_cursor = ""

        async for batch in subgraph_indexer.fetch_all_events(asset_ids=all_token_ids):
            new_in_batch = 0
            batch_tx_hashes: list[str] = []
            batch_new_wallets: set[str] = set()

            for event in batch:
                trade_data = _parse_event_to_trade(
                    event, condition_id, yes_token, no_token
                )
                tx_hash = trade_data["transaction_hash"]
                if not tx_hash:
                    continue

                # Upsert trade (ignore duplicates)
                existing = await Trade.find_one(Trade.transaction_hash == tx_hash)
                if not existing:
                    t = Trade(**trade_data)
                    try:
                        await t.insert()
                        new_in_batch += 1
                    except Exception:
                        pass
                batch_tx_hashes.append(tx_hash)
                trade_count += 1
                last_cursor = event.get("id", "")

                for addr in (trade_data.get("maker", ""), trade_data.get("taker", "")):
                    if addr and addr != NULL_ADDRESS:
                        wallet_addresses.add(addr)
                        if addr not in enriched_wallets:
                            batch_new_wallets.add(addr)

            batches_processed += 1

            # Enrich wallets seen for the first time in this batch
            if batch_new_wallets:
                await self._enrich_wallets_inline(list(batch_new_wallets))
                enriched_wallets.update(batch_new_wallets)

            # Score the trades from this batch now that wallets are enriched
            batch_scored = await self._score_batch_inline(
                condition_id, batch_tx_hashes, market
            )
            scored_count += batch_scored

            logger.info(
                f"[{condition_id}] Batch {batches_processed}: "
                f"+{new_in_batch} new trades, scored={batch_scored}, total={trade_count}"
            )

            # Update Redis job state after every batch (scored count is live)
            await ingest_job.update_job(
                condition_id,
                tradesIndexed=trade_count,
                walletsFound=len(wallet_addresses),
                batchesProcessed=batches_processed,
                scoredCount=scored_count,
                lastCursor=last_cursor,
            )

        logger.info(
            f"Ingestion complete for {condition_id}: "
            f"{trade_count} trades, {len(wallet_addresses)} wallets, {scored_count} scored"
        )

        if trade_count == 0:
            if batches_processed == 0:
                msg = (
                    "No trades fetched — subgraph returned empty on first batch. "
                    f"Token IDs used: {all_token_ids}. "
                    "Possible causes: wrong token IDs, market too old for subgraph index, "
                    "or transient subgraph unavailability."
                )
            else:
                msg = (
                    f"No trades found after {batches_processed} batch(es). "
                    "Market may be genuinely empty."
                )
            logger.warning(f"[{condition_id}] {msg}")
            await ingest_job.add_warning(condition_id, msg)

        # ── Step 4: Update market verdict from all scored InsiderScore docs ───
        await self._update_market_verdict(condition_id, market)

        # ── Step 5: Mark job done ─────────────────────────────────────────────
        await ingest_job.complete_job(condition_id, trade_count, len(wallet_addresses))
        logger.info(f"Ingestion job marked DONE for {condition_id}")

    async def _resolve_market(self, condition_id: str) -> Market | None:
        """Fetch market from Gamma API or return existing DB record."""
        gm_list = await market_service._get(
            "/markets", params={"condition_ids": condition_id}
        )
        if isinstance(gm_list, list) and gm_list:
            return await market_service.upsert_market(gm_list[0])
        return await Market.find_one(Market.condition_id == condition_id)

    async def _enrich_wallets_inline(self, wallet_addresses: list[str]) -> None:
        """Ensure wallet stubs exist, fetch deposit history, and update stats."""
        from app.services.indexer.deposit_indexer import deposit_indexer
        from app.services.wallet_service import wallet_service

        # Create stubs for any wallet not yet in DB
        for addr in wallet_addresses:
            existing = await Wallet.find_one(Wallet.address == addr)
            if not existing:
                try:
                    await Wallet(address=addr).insert()
                except Exception:
                    pass

        # Fetch on-chain deposit history (first_deposit_timestamp etc.)
        try:
            await deposit_indexer.index_wallets(wallet_addresses)
        except Exception as e:
            logger.warning(f"Deposit indexing failed for batch: {e}")

        # Update aggregate stats used by scoring (markets_traded, total_volume_usdc, …)
        for addr in wallet_addresses:
            try:
                await wallet_service.update_wallet_stats(addr)
            except Exception as e:
                logger.warning(f"Stat update failed for {addr}: {e}")

    async def _score_batch_inline(
        self,
        condition_id: str,
        tx_hashes: list[str],
        market: Market,
    ) -> int:
        """Score the specific trades (by tx hash) from one batch. Returns scored count."""
        from app.scorer.engine import scoring_engine

        scored = 0
        for tx_hash in tx_hashes:
            trade = await Trade.find_one(Trade.transaction_hash == tx_hash)
            if not trade:
                continue
            wallet = await Wallet.find_one(Wallet.address == trade.maker)
            if not wallet:
                wallet = Wallet(address=trade.maker)
                try:
                    await wallet.insert()
                except Exception:
                    pass
            try:
                await scoring_engine.score_trade(trade, wallet, market)
                scored += 1
            except Exception as e:
                logger.warning(f"Failed to score trade {tx_hash}: {e}")
        return scored

    async def _update_market_verdict(self, condition_id: str, market: Market) -> None:
        """Recompute market-level verdict/confidence from all InsiderScore docs."""
        from app.models.insider_score import InsiderScore

        scores = await InsiderScore.find(InsiderScore.condition_id == condition_id).to_list()
        if not scores:
            return

        max_score_doc = max(scores, key=lambda s: s.composite_score)
        top_trade = await Trade.find_one(Trade.transaction_hash == max_score_doc.trade_id)

        market.verdict = max_score_doc.classification
        market.confidence = int(max_score_doc.composite_score * 100)
        market.direction = top_trade.direction if top_trade else market.direction
        market.trader_count = len({s.wallet_address for s in scores})
        market.last_updated = datetime.now(timezone.utc)
        await market.save()
        logger.info(
            f"Market verdict updated: {condition_id} → {market.verdict} "
            f"({market.confidence}% confidence)"
        )

    # ── Backward-compat alias used by existing background_tasks calls ─────────
    async def backfill_market(self, condition_id: str) -> None:
        await self.ingest_market(condition_id)


backfill_orchestrator = BackfillOrchestrator()
