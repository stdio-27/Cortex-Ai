import json
import time
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EVENT_VERSION = "1.0"

EventType = Literal["STATUS_UPDATE", "TOKEN_STREAM", "AWAITING_INPUT", "ERROR", "COMPLETED"]
Stage = Literal["planner", "search", "synthesizing", "verification", "critique", "finished"]

# Maps the step labels used inside the LangGraph nodes (and free-form variants)
# onto the closed set of stages the frontend understands.
STAGE_ALIASES: Dict[str, Stage] = {
    "planner": "planner",
    "planning": "planner",
    "search": "search",
    "searching": "search",
    "sanitization": "search",
    "synthesizing": "synthesizing",
    "synthesizer": "synthesizing",
    "synthesis": "synthesizing",
    "verification": "verification",
    "verifying": "verification",
    "critique": "critique",
    "critiquing": "critique",
    "finished": "finished",
    "done": "finished",
}


def normalize_stage(raw: str, default: Stage = "planner") -> Stage:
    """Map an arbitrary step label onto a valid `Stage`; unknown labels use `default`."""
    return STAGE_ALIASES.get(str(raw).strip().lower(), default)


def job_channel(job_id: str) -> str:
    """Redis Pub/Sub channel (Redis DB 1) carrying the SSE events of one job."""
    return f"job_updates:{job_id}"


class SystemEventV1(BaseModel):
    """Versioned envelope for every event pushed to the SSE stream.

    The wire format is stable: the React client can rely on all six top-level
    keys always being present and correctly typed.
    """

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = EVENT_VERSION
    job_id: str = Field(min_length=1)
    event_type: EventType
    stage: Stage
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    @field_validator("data", mode="before")
    @classmethod
    def _make_data_json_safe(cls, value: Any) -> Any:
        """Coerce `data` into pure JSON types.

        Exceptions, datetimes, ObjectIds and other non-serializable values are
        stringified instead of blowing up `model_dump_json()` mid-pipeline.
        """
        if value is None:
            return {}
        if not isinstance(value, dict):
            return value
        return json.loads(json.dumps(value, default=str))

    @property
    def channel(self) -> str:
        return job_channel(self.job_id)

    def to_wire(self) -> str:
        """Serialized JSON string published on Redis and forwarded verbatim over SSE."""
        return self.model_dump_json()
