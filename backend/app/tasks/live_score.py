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


@celery_app.task(name="app.tasks.live_score.live_score_task")
def live_score_task(trade_data: dict) -> None:
    _run_async(_process_live_trade(trade_data))
