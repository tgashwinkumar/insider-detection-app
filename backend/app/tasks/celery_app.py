from celery import Celery
from app.config import settings

celery_app = Celery(
    "sentinel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.enrich_wallets",
        "app.tasks.score_market",
        "app.tasks.live_score",
        "app.tasks.refresh_markets",
        "app.tasks.ingest_market",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "refresh-markets-every-10-minutes": {
            "task": "app.tasks.refresh_markets.refresh_markets_task",
            "schedule": 600.0,  # 10 minutes
        }
    },
)
