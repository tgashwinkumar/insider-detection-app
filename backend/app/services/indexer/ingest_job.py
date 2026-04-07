"""
Redis-backed job tracker for historical ingestion tasks.

Key schema:
  sentinel:ingest:{conditionId}  →  JSON hash of job state
  sentinel:ingest_lock:{conditionId}  →  mutex (TTL 30s) prevents duplicate starts
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

KEY_PREFIX = "sentinel:ingest:"
LOCK_PREFIX = "sentinel:ingest_lock:"
JOB_TTL_SECONDS = 86400  # 24 hours


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def _job_key(condition_id: str) -> str:
    return f"{KEY_PREFIX}{condition_id.lower()}"


def _lock_key(condition_id: str) -> str:
    return f"{LOCK_PREFIX}{condition_id.lower()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def acquire_lock(condition_id: str) -> bool:
    """
    Try to acquire a run-once lock. Returns True if acquired, False if already locked.
    Lock expires in 30s automatically (prevents stuck locks on crash).
    """
    try:
        from app.redis_client import get_redis
        redis = get_redis()
        acquired = await redis.set(_lock_key(condition_id), "1", nx=True, ex=3600)  # 1 hour
        return bool(acquired)
    except Exception as e:
        logger.warning(f"Could not acquire lock for {condition_id}: {e}")
        return True  # Allow proceeding if Redis is unavailable


async def release_lock(condition_id: str) -> None:
    try:
        from app.redis_client import get_redis
        redis = get_redis()
        await redis.delete(_lock_key(condition_id))
    except Exception:
        pass


async def create_job(condition_id: str, status: str = JobStatus.RUNNING) -> dict:
    state = {
        "conditionId": condition_id,
        "status": status,
        "tradesIndexed": 0,
        "walletsFound": 0,
        "batchesProcessed": 0,
        "lastCursor": "",
        "startedAt": _now_iso(),
        "completedAt": None,
        "error": None,
        "warnings": [],      # non-fatal per-batch issues (partial query failures)
    }
    await _save(condition_id, state)
    return state


async def add_warning(condition_id: str, warning: str) -> None:
    """Append a non-fatal warning to the job state so it's visible in the status API."""
    state = await get_job(condition_id) or {}
    warnings = state.get("warnings") or []
    warnings.append(warning)
    state["warnings"] = warnings
    await _save(condition_id, state)


async def create_pending_job(condition_id: str) -> dict:
    """Create a job in PENDING state (used by router before background task starts)."""
    return await create_job(condition_id, status=JobStatus.PENDING)


async def update_job(condition_id: str, **kwargs) -> None:
    state = await get_job(condition_id) or {}
    state.update(kwargs)
    await _save(condition_id, state)


async def complete_job(condition_id: str, trades: int, wallets: int) -> None:
    await update_job(
        condition_id,
        status=JobStatus.DONE,
        tradesIndexed=trades,
        walletsFound=wallets,
        completedAt=_now_iso(),
    )


async def fail_job(condition_id: str, error: str) -> None:
    await update_job(
        condition_id,
        status=JobStatus.FAILED,
        completedAt=_now_iso(),
        error=error[:500],
    )


async def get_job(condition_id: str) -> Optional[dict]:
    try:
        from app.redis_client import get_redis
        redis = get_redis()
        raw = await redis.get(_job_key(condition_id))
        if raw:
            return json.loads(raw)
        return None
    except Exception:
        return None


async def is_job_running(condition_id: str) -> bool:
    """Return True only if the job is actively RUNNING (prevents concurrent runs).
    DONE and FAILED are intentionally excluded so those markets can be re-ingested."""
    job = await get_job(condition_id)
    if not job:
        return False
    return job.get("status") == JobStatus.RUNNING


async def _save(condition_id: str, state: dict) -> None:
    try:
        from app.redis_client import get_redis
        redis = get_redis()
        await redis.set(_job_key(condition_id), json.dumps(state), ex=JOB_TTL_SECONDS)
    except Exception as e:
        logger.warning(f"Could not persist job state for {condition_id}: {e}")
