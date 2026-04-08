import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _recover_pending_ingest_jobs() -> None:
    """
    On startup, find any ingest jobs left in PENDING state from a previous run
    (the in-memory BackgroundTask queue was lost on restart) and re-dispatch them.
    """
    try:
        import json
        from app.redis_client import get_redis
        from app.services.indexer.ingest_job import JobStatus, KEY_PREFIX

        redis = get_redis()
        recovered = 0

        async for key in redis.scan_iter(f"{KEY_PREFIX}*"):
            try:
                raw = await redis.get(key)
                if not raw:
                    continue
                job = json.loads(raw)
                if job.get("status") != JobStatus.PENDING:
                    continue

                condition_id = job.get("conditionId", "")
                if not condition_id:
                    continue

                # Try Celery first; skip if both unavailable (will stay PENDING)
                dispatched = False
                try:
                    from app.tasks.ingest_market import ingest_market_task
                    ingest_market_task.delay(condition_id)
                    dispatched = True
                except Exception:
                    pass

                if dispatched:
                    recovered += 1
                    logger.info(f"Recovered PENDING ingest job: {condition_id}")
            except Exception:
                pass

        if recovered:
            logger.info(f"Startup recovery: re-dispatched {recovered} PENDING ingest job(s)")
    except Exception as e:
        logger.warning(f"Startup recovery scan failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting SENTINEL backend...")

    from app.database import init_database
    from app.redis_client import init_redis

    await init_database()
    await init_redis()

    # Re-dispatch any markets that were PENDING when the server last shut down.
    # These were queued in-memory (BackgroundTasks or Celery) but never reached
    # RUNNING — the in-process queue was lost on restart.
    await _recover_pending_ingest_jobs()

    # Start live event listener
    # Commenting out live listener - to check for bandwidth availability for subgraphs
    # try:
    #     from app.services.indexer.live_listener import start_live_listener
    #     start_live_listener()
    # except Exception as e:
    #     logger.warning(f"Live listener failed to start: {e}")

    logger.info("SENTINEL backend ready")
    yield

    # Shutdown
    logger.info("Shutting down SENTINEL backend...")
    from app.database import close_database
    from app.redis_client import close_redis
    # from app.services.indexer.live_listener import stop_live_listener
    from app.utils.etherscan import etherscan_client
    from app.services.market_service import market_service

    # stop_live_listener()
    await close_database()
    await close_redis()
    await etherscan_client.close()
    await market_service.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="SENTINEL API",
    description="Insider trading detection for Polymarket",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # uses property
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from app.routers import markets, wallets, alerts, ws, ingest

app.include_router(markets.router)
app.include_router(wallets.router)
app.include_router(alerts.router)
app.include_router(ws.router)
app.include_router(ingest.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/")
async def root():
    return {"message": "SENTINEL — Insider Trading Detection API", "docs": "/docs"}
