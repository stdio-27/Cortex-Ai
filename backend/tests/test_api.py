import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import json

@pytest.mark.asyncio
async def test_create_job_valid(mock_mongo, mock_celery):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/jobs", json={"query": "test query"})
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    
    # Verify Mongo insert_one was called
    assert mock_mongo.insert_one.called
    
    # Verify Celery task was dispatched
    mock_celery.assert_called_once_with('process_job', args=[data["job_id"]])

@pytest.mark.asyncio
async def test_create_job_empty_query(mock_mongo, mock_celery):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Test empty string rejected
        res_empty = await ac.post("/api/jobs", json={"query": ""})
        assert res_empty.status_code == 422

        # Test missing query rejected
        res_missing = await ac.post("/api/jobs", json={})
        assert res_missing.status_code == 422

        # Ensure task was never dispatched
        assert not mock_celery.called

@pytest.mark.asyncio
async def test_get_job(mock_mongo):
    mock_mongo.find_one.return_value = {
        "_id": "dummy_mongo_id",
        "job_id": "123",
        "query": "test query",
        "status": "COMPLETED",
        "report": "This is a report"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/jobs/123")
        
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "123"
    assert data["status"] == "COMPLETED"
    assert data["report"] == "This is a report"
    assert "_id" not in data

@pytest.mark.asyncio
async def test_get_job_not_found(mock_mongo):
    mock_mongo.find_one.return_value = None
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/jobs/999")
        
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_stream_job_updates(mock_redis):
    # httpx.AsyncClient supports testing streaming responses
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with ac.stream("GET", "/api/jobs/123/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            # Read first chunk
            async for chunk in response.aiter_text():
                assert "data: " in chunk
                assert '"step": "DONE"' in chunk
                break


def _event(event_type, stage, step):
    return json.dumps({
        "version": "1.0", "job_id": "123", "event_type": event_type, "stage": stage,
        "data": {"step": step}, "timestamp": 0.0,
    })


async def _read_stream(path="/api/jobs/123/stream"):
    chunks = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with ac.stream("GET", path) as response:
            async for chunk in response.aiter_text():
                chunks.append(chunk)
    return "".join(chunks)


@pytest.mark.asyncio
async def test_stream_replays_terminal_event_for_late_subscriber(mock_redis):
    # Job finished before the client connected: snapshot is replayed, stream closes.
    mock_redis.client.get.return_value = _event("COMPLETED", "finished", "DONE").encode()
    mock_redis.get_message.side_effect = AssertionError("must not wait for live events")

    body = await _read_stream()

    assert body.count("data: ") == 1 and '"event_type": "COMPLETED"' in body
    mock_redis.client.get.assert_awaited_once_with("job_last_event:123")
    mock_redis.subscribe.assert_awaited_once_with("job_updates:123")


@pytest.mark.asyncio
async def test_stream_replays_snapshot_then_continues_live_without_duplicates(mock_redis):
    snapshot = _event("STATUS_UPDATE", "search", "Search")
    mock_redis.client.get.return_value = snapshot.encode()
    mock_redis.get_message.side_effect = [
        {"type": "message", "data": snapshot.encode()},  # same event arriving live
        {"type": "message", "data": _event("COMPLETED", "finished", "DONE").encode()},
    ]

    body = await _read_stream()

    assert body.count('"step": "Search"') == 1
    assert body.count('"event_type": "COMPLETED"') == 1


@pytest.mark.asyncio
async def test_stream_survives_snapshot_read_failure(mock_redis):
    mock_redis.client.get.side_effect = ConnectionError("redis down")

    body = await _read_stream()

    assert '"event_type": "COMPLETED"' in body
