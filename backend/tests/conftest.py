import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.main import app

@pytest.fixture
def mock_mongo(mocker):
    # Mock MongoDB client
    mock_db = MagicMock()
    mock_collection = MagicMock()
    
    # Setup AsyncMocks for collection methods
    mock_collection.insert_one = AsyncMock()
    mock_collection.find_one = AsyncMock()
    
    # Chain them: client[db_name][collection_name]
    mock_db.__getitem__.return_value = mock_collection
    
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    
    mocker.patch("app.api.routes.db.async_client", new=mock_client)
    return mock_collection

@pytest.fixture
def mock_celery(mocker):
    # Mock celery send_task to avoid running real workers
    return mocker.patch("app.api.routes.celery_app.send_task")

@pytest.fixture
def mock_redis(mocker):
    # Mock Redis client for SSE streaming
    mock_client = MagicMock()
    mock_pubsub = MagicMock()
    
    # Mock pubsub methods
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.parse_response = AsyncMock(return_value=[b"subscribe", b"job_updates:123", 1])
    mock_pubsub.aclose = AsyncMock()
    
    # Mock get_message to return a dummy DONE message to end the stream
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {"type": "message", "data": json.dumps({
            "version": "1.0", "job_id": "123", "event_type": "COMPLETED", "stage": "finished",
            "data": {"step": "DONE", "status": "COMPLETED"}, "timestamp": 0.0,
        }).encode()}
    ])
    
    mock_client.pubsub.return_value = mock_pubsub
    mock_client.get = AsyncMock(return_value=None)
    mock_client.delete = AsyncMock()
    mocker.patch("app.api.routes.get_async_redis_pubsub_client", return_value=mock_client)
    mock_pubsub.client = mock_client
    return mock_pubsub
