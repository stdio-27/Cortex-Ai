import asyncio
import json
import logging
import math
import random
import traceback as traceback_module
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery.signals import task_failure

from app.agent.agent_runner import run_agent
from app.core.config import settings
from app.core.redis import get_redis_client, get_redis_pubsub_client
from app.db.mongo import connect_to_mongo_sync, db
from app.services.llm_service import (
    is_rate_limit_error,
    is_transient_llm_error,
    retry_after_seconds,
)
from app.services.pubsub_service import PubSubService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

PROCESS_JOB_TASK_NAME = "process_job"

# Lock TTL must exceed the task hard time limit so a live task never loses its lock.
TASK_SOFT_TIME_LIMIT_SECONDS = 780
TASK_TIME_LIMIT_SECONDS = 840
LOCK_TTL_SECONDS = 900

MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 5
BACKOFF_CAP_SECONDS = 300

DLQ_REDIS_KEY = "dlq:failed_jobs"
DLQ_REDIS_MAX_LEN = 10000
DLQ_COLLECTION = "dead_letter_jobs"

# Compare-and-delete: only the owner of the lock may release it.
_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


class JobLock:
    """Redis distributed lock `lock:job:{job_id}` (broker Redis, DB 0)."""

    def __init__(self, redis_client: Any, job_id: str, owner: str, ttl: int = LOCK_TTL_SECONDS):
        self.redis_client = redis_client
        self.key = f"lock:job:{job_id}"
        self.token = f"{owner}:{uuid.uuid4().hex}"
        self.ttl = ttl
        self.acquired = False

    def acquire(self) -> bool:
        self.acquired = bool(self.redis_client.set(self.key, self.token, nx=True, ex=self.ttl))
        return self.acquired

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.redis_client.eval(_RELEASE_LOCK_LUA, 1, self.key, self.token)
        except Exception as exc:
            # The TTL is the safety net; never mask the task's real outcome.
            logger.warning("Failed to release %s (will expire via TTL): %s", self.key, exc)
        finally:
            self.acquired = False


def _compute_countdown(retries: int, exc: BaseException) -> int:
    backoff = min(BACKOFF_BASE_SECONDS * (2 ** retries), BACKOFF_CAP_SECONDS)
    backoff += random.uniform(0, BACKOFF_BASE_SECONDS)
    hint = retry_after_seconds(exc)
    if hint is not None:
        backoff = max(backoff, hint + 1)
    return int(math.ceil(backoff))


def _publish_retry_event(job_id: str, exc: BaseException, countdown: int, attempt: int) -> None:
    """Tell the UI the job is waiting, without moving the stepper.

    `step` is deliberately omitted: the frontend treats any `step` as the new
    current step, and a non-stage value would derail the progress indicator.
    """
    try:
        service = PubSubService(get_redis_pubsub_client())
        service.publish_status(
            job_id,
            service.last_stage(job_id) or "planner",
            {
                "status": "RETRYING",
                "reason": "RATE_LIMITED" if is_rate_limit_error(exc) else "TRANSIENT_LLM_ERROR",
                "retry_in_seconds": countdown,
                "attempt": attempt,
                "max_retries": MAX_RETRIES,
            },
        )
    except Exception as publish_exc:
        logger.warning("Could not publish retry event for job %s: %s", job_id, publish_exc)


@celery_app.task(
    name=PROCESS_JOB_TASK_NAME,
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=TASK_SOFT_TIME_LIMIT_SECONDS,
    time_limit=TASK_TIME_LIMIT_SECONDS,
)
def process_job(self, job_id: str, resume_data: Optional[dict] = None):
    redis_client = get_redis_client()
    lock = JobLock(redis_client, job_id, owner=str(self.request.id))

    if not lock.acquire():
        logger.info("Job %s is already being processed; skipping duplicate dispatch.", job_id)
        return {"job_id": job_id, "status": "SKIPPED_DUPLICATE"}

    try:
        logger.info("Starting job %s (attempt %s).", job_id, self.request.retries + 1)
        asyncio.run(run_agent(job_id, resume_data))
        return {"job_id": job_id, "status": "COMPLETED"}
    except Exception as exc:
        if is_rate_limit_error(exc) or is_transient_llm_error(exc):
            retries = self.request.retries
            countdown = _compute_countdown(retries, exc)
            if retries < MAX_RETRIES:
                logger.warning(
                    "Job %s hit a retryable LLM error (%s). Retry %s/%s in %ss.",
                    job_id, type(exc).__name__, retries + 1, MAX_RETRIES, countdown,
                )
                _publish_retry_event(job_id, exc, countdown, retries + 1)
            # Hand the job back to the broker instead of sleeping in this worker.
            # Once retries are exhausted, retry() re-raises `exc`, which fires
            # task_failure and lands the job in the DLQ. The lock is released by
            # the finally block below before the retry becomes visible.
            raise self.retry(exc=exc, countdown=countdown, max_retries=MAX_RETRIES)
        raise
    finally:
        lock.release()


# --------------------------------------------------------------------------- #
# Dead-letter queue                                                            #
# --------------------------------------------------------------------------- #
def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _sync_db():
    if db.sync_client is None:
        connect_to_mongo_sync()
    return db.sync_client[settings.MONGODB_DB_NAME]


def _extract_job_id(args: Any, kwargs: Any) -> Optional[str]:
    if args and isinstance(args[0], str):
        return args[0]
    if isinstance(kwargs, dict) and isinstance(kwargs.get("job_id"), str):
        return kwargs["job_id"]
    return None


def _user_facing_error(exc: BaseException) -> str:
    if is_rate_limit_error(exc):
        return "The AI provider is rate limiting requests. Please try again in a few minutes."
    return f"{type(exc).__name__}: {str(exc)[:300]}"


@task_failure.connect
def handle_task_failure(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    kwargs=None,
    traceback=None,
    einfo=None,
    **other,
):
    """Terminal-failure hook: persist forensics, enqueue to the DLQ, notify the UI.

    Fires only for failures that will not be retried again. Each side effect is
    isolated so that, for example, a MongoDB outage still lets the Redis DLQ
    entry and the UI error event go out.
    """
    try:
        job_id = _extract_job_id(args, kwargs)
        request = getattr(sender, "request", None)
        retry_count = getattr(request, "retries", 0) or 0

        if einfo is not None and getattr(einfo, "traceback", None):
            trace_text = str(einfo.traceback)
        elif exception is not None:
            trace_text = "".join(
                traceback_module.format_exception(type(exception), exception, exception.__traceback__)
            )
        else:
            trace_text = ""

        failed_at = datetime.now(timezone.utc)
        envelope: Dict[str, Any] = {
            "task_id": task_id,
            "job_id": job_id or "unknown",
            "task_name": getattr(sender, "name", "unknown"),
            "error_type": type(exception).__name__ if exception is not None else "Unknown",
            "error": str(exception),
            "traceback": trace_text,
            "payload": _json_safe({"args": list(args or []), "kwargs": kwargs or {}}),
            "retry_count": retry_count,
            "max_retries": MAX_RETRIES,
            "rate_limited": bool(exception is not None and is_rate_limit_error(exception)),
            "failed_at": failed_at.isoformat(),
        }
    except Exception as exc:
        logger.error("DLQ handler could not build the failure envelope: %s", exc)
        return

    # 1. MongoDB: durable forensics. Upsert on task_id keeps the hook idempotent
    #    and avoids insert_one() mutating `envelope` with a non-JSON ObjectId.
    try:
        _sync_db()[DLQ_COLLECTION].update_one(
            {"task_id": task_id},
            {"$set": {**envelope, "failed_at_dt": failed_at}},
            upsert=True,
        )
    except Exception as exc:
        logger.error("DLQ: MongoDB write failed for job %s: %s", envelope["job_id"], exc)

    # 2. Redis: work-queue view of the DLQ for operators/replay tooling.
    try:
        redis_client = get_redis_client()
        redis_client.lpush(DLQ_REDIS_KEY, json.dumps(envelope, default=str))
        redis_client.ltrim(DLQ_REDIS_KEY, 0, DLQ_REDIS_MAX_LEN - 1)
    except Exception as exc:
        logger.error("DLQ: Redis push failed for job %s: %s", envelope["job_id"], exc)

    if not job_id:
        return

    # 3. Mark the job FAILED so GET /jobs/{id} agrees with the stream.
    try:
        _sync_db()["jobs"].update_one(
            {"job_id": job_id, "status": {"$ne": "COMPLETED"}},
            {"$set": {"status": "FAILED", "error": _user_facing_error(exception)}},
        )
    except Exception as exc:
        logger.error("DLQ: could not mark job %s FAILED: %s", job_id, exc)

    # 4. Tell the UI, with a clean typed envelope, that the job is dead.
    try:
        service = PubSubService(get_redis_pubsub_client())
        service.publish_status(
            job_id,
            "finished",
            {
                "step": "ERROR",
                "status": "FAILED",
                "error": _user_facing_error(exception),
                "failed_stage": service.last_stage(job_id),
                "dead_lettered": True,
            },
            event_type="ERROR",
        )
    except Exception as exc:
        logger.error("DLQ: could not publish ERROR event for job %s: %s", job_id, exc)
