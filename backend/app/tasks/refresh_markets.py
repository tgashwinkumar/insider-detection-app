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


async def _refresh() -> None:
    from app.database import init_database
    from app.services.market_service import market_service

    await init_database()

    # Fetch recent active markets from Gamma API
    data = await market_service._get("/markets", params={"active": "true", "limit": "100"})
    if not isinstance(data, list):
        return

    for gm in data:
        try:
            await market_service.upsert_market(gm)
        except Exception as e:
            logger.warning(f"Failed to upsert market: {e}")

    logger.info(f"Refreshed {len(data)} markets from Gamma API")


@celery_app.task(name="app.tasks.refresh_markets.refresh_markets_task")
def refresh_markets_task() -> None:
    _run_async(_refresh())
