import json
from unittest.mock import MagicMock, patch

import fakeredis
import groq
import httpx
import pytest
from celery.exceptions import Retry

from app.schemas.events import SystemEventV1, normalize_stage
from app.services.pubsub_service import PubSubService
from app.services import llm_service
from app.services.llm_service import LLMService, is_rate_limit_error, retry_after_seconds
from langchain_core.messages import AIMessage


def make_429():
    req = httpx.Request("POST", "https://api.groq.com/x")
    resp = httpx.Response(429, headers={"retry-after": "12"}, request=req)
    return groq.RateLimitError("rate limited", response=resp, body=None)


def test_event_schema():
    e = SystemEventV1(job_id="j", event_type="ERROR", stage="finished", data={"e": ValueError("x"), "ok": 1})
    d = json.loads(e.to_wire())
    assert set(d) == {"version", "job_id", "event_type", "stage", "data", "timestamp"} and d["version"] == "1.0"
    assert d["data"]["e"] == "x"
    with pytest.raises(Exception):
        SystemEventV1(job_id="j", event_type="BOGUS", stage="finished")
    assert normalize_stage("Critiquing") == "critique"


def test_pubsub_db1_channel():
    r = fakeredis.FakeRedis()
    ps = r.pubsub()
    ps.subscribe("job_updates:j")
    ps.get_message()
    svc = PubSubService(r)
    assert svc.publish_update("j", "Critiquing", "IN_PROGRESS")
    msg = ps.get_message()
    assert json.loads(msg["data"])["stage"] == "critique"
    assert svc.last_stage("j") == "critique"


def test_llm_errors_and_json():
    exc = make_429()
    assert is_rate_limit_error(exc) and retry_after_seconds(exc) == 12.0
    assert not is_rate_limit_error(ValueError("nope"))
    svc = LLMService("m", "m", "key")
    good = '```json\n{"verification_score": 140, "supported_claims_count": 3, "unverified_claims": ["a"], "confidence_tier": "high"}\n```'
    with patch.object(type(svc.llm), "invoke", return_value=AIMessage(content=good)):
        out = svc.verify_report("draft {with} braces {x:y}", [{"a": "{b}"}])
    assert out["verification_score"] == 100.0 and out["confidence_tier"] == "HIGH"
    with patch.object(type(svc.llm), "invoke", return_value=AIMessage(content="sorry, no json")):
        assert svc.verify_report("d", [])["verification_status"] == "UNAVAILABLE"
    with patch.object(type(svc.llm), "invoke", side_effect=exc):
        with pytest.raises(groq.RateLimitError):
            svc.verify_report("d", [])


def test_prompts_with_braces_do_not_template():
    svc = LLMService("m", "m", "key")
    seen = {}

    def fake(self, messages, *a, **k):
        seen["m"] = messages
        return AIMessage(content="ok")

    with patch.object(type(svc.llm), "invoke", fake):
        svc.synthesize_report('q {"a": {b:c}} {0:>x}', "{}", "{x!r:}")
    assert "{0:>x}" in seen["m"][1].content


def test_task_lock_retry_dlq():
    import app.worker.tasks as t
    r = fakeredis.FakeRedis()
    pub = fakeredis.FakeRedis()
    jobs = MagicMock()
    dbmock = MagicMock()
    dbmock.__getitem__.return_value = jobs
    t.db.sync_client = MagicMock()
    t.db.sync_client.__getitem__.return_value = dbmock

    async def boom(job_id, resume):
        assert r.exists(f"lock:job:{job_id}")
        raise make_429()

    with patch.object(t, "get_redis_client", return_value=r), \
         patch.object(t, "get_redis_pubsub_client", return_value=pub), \
         patch.object(t, "run_agent", boom):
        # retry path: lock released, Retry raised
        with pytest.raises(Retry):
            t.process_job.apply(args=["job1"], throw=True).get()
        assert not r.exists("lock:job:job1")

        # duplicate dispatch skipped
        r.set("lock:job:job2", "other", ex=60)
        res = t.process_job.apply(args=["job2"]).get()
        assert res["status"] == "SKIPPED_DUPLICATE"
        assert r.get("lock:job:job2") == b"other"  # not stolen / not released

    # DLQ hook
    with patch.object(t, "get_redis_client", return_value=r), \
         patch.object(t, "get_redis_pubsub_client", return_value=pub):
        ps = pub.pubsub(); ps.subscribe("job_updates:job9"); ps.get_message()
        t.handle_task_failure(sender=t.process_job, task_id="tid", exception=ValueError("bad"),
                              args=["job9"], kwargs={}, einfo=None)
        assert r.llen("dlq:failed_jobs") == 1
        entry = json.loads(r.lindex("dlq:failed_jobs", 0))
        assert entry["job_id"] == "job9" and entry["error_type"] == "ValueError"
        ev = json.loads(ps.get_message()["data"])
        assert ev["event_type"] == "ERROR" and ev["stage"] == "finished"
        dbmock.__getitem__.assert_any_call("dead_letter_jobs")
