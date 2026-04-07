"""
Ingest router — expose historical data ingestion as a first-class API.

Endpoints:
  GET /api/ingest?q={slug|url|conditionId}
      → Resolve the query to one or more conditionIds (events have multiple markets),
        start a Celery ingestion task per market, return immediately with all job states.
        PENDING and RUNNING markets are skipped (already queued/running).
        DONE and FAILED markets are re-ingested on every call.

  GET /api/ingest/{conditionId}/status
      → Read current job state from Redis for a single market.

  DELETE /api/ingest/{conditionId}/reset
      → Clear a job's Redis state and immediately re-dispatch ingestion.
"""
import logging
from fastapi import APIRouter, HTTPException, Query

from app.services.market_service import market_service
from app.services.indexer import ingest_job
from app.services.indexer.ingest_job import JobStatus, create_pending_job

logger = logging.getLogger(__name__)
router = APIRouter()

# Only PENDING and RUNNING block re-dispatch.
# DONE and FAILED markets are re-ingested every time the endpoint is called.
_ACTIVE_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING)


async def _resolve_all_markets(q: str) -> list[dict]:
    """
    Resolve any query → list of Gamma market dicts.

    - conditionId  → single market via /markets?condition_ids=
    - URL (event)  → all child markets via /events/slug/
    - URL (market) → single market via /markets/slug/
    - tokenId      → single market via /markets?token_id=
    - text         → up to 20 markets via slug_contains search
    """
    return await market_service.search_markets(q, limit=50)


def _dispatch(condition_id: str) -> None:
    """Dispatch an ingest_market Celery task. Logs a warning if Celery is unavailable."""
    try:
        from app.tasks.ingest_market import ingest_market_task
        ingest_market_task.delay(condition_id)
        logger.info(f"Celery task dispatched for {condition_id}")
    except Exception as e:
        logger.warning(f"Celery dispatch failed for {condition_id}: {e}")


@router.get("/api/ingest")
async def start_ingest(
    q: str = Query(..., description="Polymarket URL, slug, or condition ID"),
):
    """
    Resolve query → one or more markets, dispatch a Celery ingestion task per market.
    Returns immediately. Poll /api/ingest/{conditionId}/status for each market.

    Markets that are PENDING or RUNNING are returned as alreadyRunning=True and skipped.
    Markets that are DONE or FAILED are re-ingested on every call.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    gamma_markets = await _resolve_all_markets(q)
    if not gamma_markets:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve any markets from query: {q}",
        )

    jobs = []
    for gm in gamma_markets:
        condition_id = (
            gm.get("conditionId") or gm.get("condition_id") or ""
        ).lower()
        if not condition_id:
            continue

        # Upsert market metadata so it's immediately queryable
        try:
            await market_service.upsert_market(gm)
        except Exception as e:
            logger.warning(f"Could not upsert market {condition_id}: {e}")

        # Skip only PENDING and RUNNING markets (already queued / actively running).
        # DONE and FAILED markets are re-dispatched so stale or failed runs are retried.
        existing = await ingest_job.get_job(condition_id)
        if existing and existing.get("status") in _ACTIVE_STATUSES:
            jobs.append({
                "conditionId": condition_id,
                "question": gm.get("question") or gm.get("title") or "",
                "alreadyRunning": True,
                **existing,
            })
            continue

        # Create PENDING job before dispatching so the status endpoint returns
        # immediately and a concurrent re-request hits the PENDING guard above.
        initial_state = await create_pending_job(condition_id)
        _dispatch(condition_id)

        jobs.append({
            "conditionId": condition_id,
            "question": gm.get("question") or gm.get("title") or "",
            "alreadyRunning": False,
            **initial_state,
        })

    if not jobs:
        raise HTTPException(
            status_code=422,
            detail="Markets found but none had a valid conditionId",
        )

    return {
        "totalMarkets": len(jobs),
        "jobs": jobs,
    }


@router.get("/api/ingest/{condition_id}/status")
async def get_ingest_status(condition_id: str):
    """Return current job state from Redis for a single market."""
    condition_id = condition_id.lower()
    job = await ingest_job.get_job(condition_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"No ingestion job found for {condition_id}. "
                   "Call GET /api/ingest?q={conditionId} to start one.",
        )
    return job


@router.delete("/api/ingest/{condition_id}/reset")
async def reset_ingest_job(condition_id: str):
    """
    Clear a job's Redis state and immediately re-dispatch ingestion via Celery.
    Useful for forcing a re-ingest without waiting for the 24-hour Redis TTL.
    Returns 409 if the market is currently RUNNING.
    """
    condition_id = condition_id.lower()
    existing = await ingest_job.get_job(condition_id)
    if existing and existing.get("status") == JobStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Ingestion for {condition_id} is currently RUNNING. Wait for it to complete.",
        )

    # Delete Redis job + lock so the Celery task sees a clean slate
    from app.redis_client import get_redis
    from app.services.indexer.ingest_job import KEY_PREFIX, LOCK_PREFIX
    redis = get_redis()
    await redis.delete(f"{KEY_PREFIX}{condition_id}")
    await redis.delete(f"{LOCK_PREFIX}{condition_id}")

    initial_state = await create_pending_job(condition_id)
    _dispatch(condition_id)

    return {
        "reset": True,
        "conditionId": condition_id,
        **initial_state,
    }
