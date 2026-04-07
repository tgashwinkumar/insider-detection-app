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
    amount_usdc = taker_amount / 1e6

    return {
        "transaction_hash": event.get("transactionHash") or event.get("id", ""),
        "block_number": int(event.get("blockNumber", 0)),
        "timestamp": ts,
        "maker": (event.get("maker") or "").lower(),
        "taker": (event.get("taker") or "").lower(),
        "maker_asset_id": event.get("makerAssetId", ""),
        "taker_asset_id": event.get("takerAssetId", ""),
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
        # fetch_all_events raises RuntimeError if ALL 4 parallel queries fail
        # (e.g. stale httpx client in a Celery worker). That exception propagates
        # to ingest_market's try-except, which calls fail_job with the error message.
        # If only SOME queries fail, fetch_order_filled_events logs those failures
        # and continues with partial results — we capture them as warnings below.
        trade_count = 0
        wallet_addresses: set[str] = set()
        batches_processed = 0
        last_cursor = ""

        async for batch in subgraph_indexer.fetch_all_events(asset_ids=all_token_ids):
            new_in_batch = 0
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
                trade_count += 1
                last_cursor = event.get("id", "")

                maker = trade_data.get("maker", "")
                taker = trade_data.get("taker", "")
                if maker and maker != NULL_ADDRESS:
                    wallet_addresses.add(maker)
                if taker and taker != NULL_ADDRESS:
                    wallet_addresses.add(taker)

            batches_processed += 1
            logger.info(
                f"[{condition_id}] Batch {batches_processed}: "
                f"+{new_in_batch} new trades, total={trade_count}"
            )

            # Update Redis job state after every batch
            await ingest_job.update_job(
                condition_id,
                tradesIndexed=trade_count,
                walletsFound=len(wallet_addresses),
                batchesProcessed=batches_processed,
                lastCursor=last_cursor,
            )

        logger.info(
            f"Ingestion complete for {condition_id}: "
            f"{trade_count} trades, {len(wallet_addresses)} wallets"
        )

        # If no trades were found after a full run, record a warning so the
        # status API can surface it.  batchesProcessed=0 means the subgraph
        # returned empty on the very first call — likely a data or query issue
        # rather than a genuinely empty market.
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

        # ── Step 4: Ensure wallet stubs exist ─────────────────────────────────
        for addr in wallet_addresses:
            existing_wallet = await Wallet.find_one(Wallet.address == addr)
            if not existing_wallet:
                w = Wallet(address=addr)
                try:
                    await w.insert()
                except Exception:
                    pass

        # ── Step 5: Enqueue enrichment + scoring ──────────────────────────────
        clean_wallets = [
            a for a in wallet_addresses
            if a and a != NULL_ADDRESS
        ]
        if clean_wallets:
            dispatched = await self._dispatch_enrichment_and_scoring(
                condition_id, clean_wallets
            )
            if not dispatched:
                # Celery unavailable — run inline (slower but always works)
                from app.services.indexer.deposit_indexer import deposit_indexer
                await deposit_indexer.index_wallets(clean_wallets)
                await self._score_market_inline(condition_id)

        # ── Step 6: Mark job done ──────────────────────────────────────────────
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

    async def _dispatch_enrichment_and_scoring(
        self, condition_id: str, wallet_addresses: list[str]
    ) -> bool:
        """Enqueue Celery chain. Returns True if dispatched, False if Celery unavailable."""
        try:
            from app.tasks.enrich_wallets import enrich_wallets_task
            from app.tasks.score_market import score_market_task
            enrich_wallets_task.apply_async(
                args=[wallet_addresses],
                link=score_market_task.si(condition_id),
            )
            logger.info(f"Celery chain dispatched for {condition_id}")
            return True
        except Exception as e:
            logger.warning(f"Celery unavailable ({e}), will run inline")
            return False

    async def _score_market_inline(self, condition_id: str) -> None:
        """Score all trades for a market directly (fallback when Celery is unavailable)."""
        from app.scorer.engine import scoring_engine
        from app.models.insider_score import InsiderScore

        trades = await Trade.find(Trade.condition_id == condition_id).to_list()
        market = await Market.find_one(Market.condition_id == condition_id)
        if not market:
            return

        scored_count = 0
        for trade in trades:
            wallet = await Wallet.find_one(Wallet.address == trade.maker)
            if not wallet:
                wallet = Wallet(address=trade.maker)
                await wallet.insert()
            try:
                await scoring_engine.score_trade(trade, wallet, market)
                scored_count += 1
            except Exception as e:
                logger.warning(f"Failed to score trade {trade.transaction_hash}: {e}")

        # Update market aggregate verdict
        scores = await InsiderScore.find(InsiderScore.condition_id == condition_id).to_list()
        if scores:
            max_score_doc = max(scores, key=lambda s: s.composite_score)
            confidence = int(max_score_doc.composite_score * 100)
            verdict = max_score_doc.classification
            top_trade = await Trade.find_one(Trade.transaction_hash == max_score_doc.trade_id)
            direction = top_trade.direction if top_trade else None

            market.verdict = verdict
            market.confidence = confidence
            market.direction = direction
            market.trader_count = len({s.wallet_address for s in scores})
            market.last_updated = datetime.now(timezone.utc)
            await market.save()

        logger.info(f"Inline scoring complete: {scored_count} trades for {condition_id}")

    # ── Backward-compat alias used by existing background_tasks calls ─────────
    async def backfill_market(self, condition_id: str) -> None:
        await self.ingest_market(condition_id)


backfill_orchestrator = BackfillOrchestrator()
