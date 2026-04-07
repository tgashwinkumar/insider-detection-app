import asyncio
import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Celery task."""
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


async def _enrich(wallet_addresses: list[str]) -> None:
    from app.database import init_database
    from app.services.indexer.deposit_indexer import deposit_indexer
    from app.services.wallet_service import wallet_service

    await init_database()
    await deposit_indexer.index_wallets(wallet_addresses)
    for addr in wallet_addresses:
        try:
            await wallet_service.update_wallet_stats(addr)
        except Exception as e:
            logger.warning(f"Failed to update stats for {addr}: {e}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.tasks.enrich_wallets.enrich_wallets_task")
def enrich_wallets_task(self, wallet_addresses: list[str]) -> None:
    try:
        _run_async(_enrich(wallet_addresses))
    except Exception as exc:
        logger.error(f"enrich_wallets_task failed: {exc}")
        raise self.retry(exc=exc, countdown=30)
