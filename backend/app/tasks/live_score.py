import asyncio
import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _process_live_trade(trade_data: dict) -> None:
    from app.database import init_database
    from app.models.trade import Trade
    from app.models.wallet import Wallet
    from app.models.market import Market
    from app.scorer.engine import scoring_engine
    from app.services.wallet_service import wallet_service

    await init_database()

    tx_hash = trade_data.get("transaction_hash", "")
    if not tx_hash:
        return

    # Upsert trade
    existing = await Trade.find_one(Trade.transaction_hash == tx_hash)
    if not existing:
        t = Trade(**trade_data)
        try:
            await t.insert()
            trade = t
        except Exception:
            trade = await Trade.find_one(Trade.transaction_hash == tx_hash)
            if not trade:
                return
    else:
        trade = existing

    # Ensure wallet exists and is enriched
    maker = trade.maker
    wallet = await wallet_service.enrich_wallet(maker)

    # Find market (may not exist for live trades without condition_id mapping)
    condition_id = trade.condition_id
    market = None
    if condition_id:
        market = await Market.find_one(Market.condition_id == condition_id)

    if not market:
        # Create a placeholder market for scoring
        market = Market(
            condition_id=condition_id or tx_hash,
            question="Unknown market (live trade)",
            resolution_date="",
        )
        # Don't save this placeholder

    try:
        await scoring_engine.score_trade(trade, wallet, market)
    except Exception as e:
        logger.error(f"Failed to score live trade {tx_hash}: {e}")
        return

    # Publish the scored trade to the per-market Redis channel so the frontend
    # WebSocket connection receives it and replaces the pending placeholder row.
    #
    # IMPORTANT: get_redis() relies on init_redis() which is only called in the
    # FastAPI process. In a Celery worker we create a direct connection instead.
    if condition_id and condition_id != tx_hash:
        try:
            import json
            import redis.asyncio as aioredis
            from app.config import settings
            from app.models.insider_score import InsiderScore
            from app.routers.markets import _trade_to_response

            score = await InsiderScore.find_one(InsiderScore.trade_id == tx_hash)
            tr = _trade_to_response(trade, score)
            if wallet and wallet.first_deposit_timestamp:
                tr["walletCreatedAt"] = wallet.first_deposit_timestamp * 1000
            tr["firstTradeAt"] = trade.timestamp * 1000

            # Include the asset IDs so the frontend can match & clear the pending placeholder
            tr["makerAssetId"] = trade.maker_asset_id
            tr["takerAssetId"] = trade.taker_asset_id

            _r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                await _r.publish(
                    f"sentinel:live:{condition_id}",
                    json.dumps({"type": "new_trade", "conditionId": condition_id, "trade": tr}),
                )
                logger.info(f"Published scored live trade {tx_hash} to sentinel:live:{condition_id}")
            finally:
                await _r.aclose()
        except Exception as pub_e:
            logger.warning(f"Failed to publish scored trade to Redis: {pub_e}")


@celery_app.task(name="app.tasks.live_score.live_score_task")
def live_score_task(trade_data: dict) -> None:
    _run_async(_process_live_trade(trade_data))
