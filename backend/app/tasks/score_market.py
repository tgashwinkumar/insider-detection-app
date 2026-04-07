import asyncio
import logging
from datetime import datetime
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


async def _score(condition_id: str) -> None:
    from app.database import init_database
    from app.models.trade import Trade
    from app.models.wallet import Wallet
    from app.models.market import Market
    from app.models.insider_score import InsiderScore
    from app.scorer.engine import scoring_engine

    await init_database()

    trades = await Trade.find(Trade.condition_id == condition_id).to_list()
    market = await Market.find_one(Market.condition_id == condition_id)
    if not market:
        logger.warning(f"Market {condition_id} not found for scoring")
        return

    scored = 0
    for trade in trades:
        wallet = await Wallet.find_one(Wallet.address == trade.maker)
        if not wallet:
            from app.models.wallet import Wallet as W
            wallet = W(address=trade.maker)
            await wallet.insert()
        try:
            await scoring_engine.score_trade(trade, wallet, market)
            scored += 1
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
        market.last_updated = datetime.utcnow()
        await market.save()

    logger.info(f"Scored {scored} trades for market {condition_id}")


@celery_app.task(name="app.tasks.score_market.score_market_task")
def score_market_task(condition_id: str) -> None:
    _run_async(_score(condition_id))
