import json
import logging
from typing import Any, Dict, Optional

from app.schemas.events import (
    EventType,
    Stage,
    SystemEventV1,
    job_channel,
    normalize_stage,
)

logger = logging.getLogger(__name__)

LAST_EVENT_KEY_PREFIX = "job_last_event:"
LAST_EVENT_TTL_SECONDS = 3600


class PubSubService:
    """Publishes validated `SystemEventV1` envelopes on the SSE Pub/Sub bus.

    The injected client MUST be the Pub/Sub client (Redis DB 1, see
    `app.core.redis.get_redis_pubsub_client`) and never the Celery broker
    client (Redis DB 0). Publishing is best-effort: a Redis hiccup must not
    abort the research pipeline, so failures are logged and reported through
    the boolean return value.
    """

    def __init__(self, redis_client: Any = None):
        if redis_client is None:
            from app.core.redis import get_redis_pubsub_client

            redis_client = get_redis_pubsub_client()
        self.redis_client = redis_client

    def publish_event(self, event: SystemEventV1) -> bool:
        payload = event.to_wire()
        try:
            self.redis_client.publish(job_channel(event.job_id), payload)
        except Exception as exc:
            logger.warning("Pub/Sub publish failed for job %s: %s", event.job_id, exc)
            return False

        # Keep the latest event so a late SSE subscriber (or the worker, when it
        # needs to know the current stage) can recover state; Pub/Sub itself is
        # fire-and-forget.
        try:
            self.redis_client.set(
                f"{LAST_EVENT_KEY_PREFIX}{event.job_id}", payload, ex=LAST_EVENT_TTL_SECONDS
            )
        except Exception as exc:
            logger.debug("Could not store last event for job %s: %s", event.job_id, exc)
        return True

    def publish_status(
        self,
        job_id: str,
        stage: Stage,
        data: Optional[Dict[str, Any]] = None,
        event_type: EventType = "STATUS_UPDATE",
    ) -> bool:
        try:
            event = SystemEventV1(
                job_id=job_id, event_type=event_type, stage=stage, data=data or {}
            )
        except Exception as exc:
            logger.error("Invalid event for job %s: %s", job_id, exc)
            return False
        return self.publish_event(event)

    def publish_update(self, job_id: str, step_name: str, status: str) -> bool:
        """Legacy node-facing API: `("Critiquing", "IN_PROGRESS")` etc."""
        return self.publish_status(
            job_id,
            normalize_stage(step_name),
            {"step": step_name, "status": status},
        )

    def last_stage(self, job_id: str) -> Optional[Stage]:
        """Stage of the most recent event published for the job, if known."""
        try:
            raw = self.redis_client.get(f"{LAST_EVENT_KEY_PREFIX}{job_id}")
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return SystemEventV1.model_validate(json.loads(raw)).stage
        except Exception:
            return None
