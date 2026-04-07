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


async def _ingest(condition_id: str) -> None:
    from app.database import init_database
    from app.redis_client import init_redis
    from app.services.indexer.backfill import backfill_orchestrator

    await init_database()
    await init_redis()
    await backfill_orchestrator.ingest_market(condition_id)


@celery_app.task(
    name="app.tasks.ingest_market.ingest_market_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def ingest_market_task(self, condition_id: str) -> None:
    """
    Celery task: run full historical ingestion for a single market.
    Retries up to 3 times on unexpected failure (60 s delay between retries).
    Job state (PENDING → RUNNING → DONE/FAILED) is managed by ingest_market().
    """
    try:
        _run_async(_ingest(condition_id))
    except Exception as exc:
        logger.exception(f"ingest_market_task failed for {condition_id}: {exc}")
        raise self.retry(exc=exc)
