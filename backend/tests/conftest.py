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
    
    mocker.patch("app.api.routes.db.client", new=mock_client)
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
    mock_pubsub.unsubscribe = AsyncMock()
    
    # Mock get_message to return a dummy DONE message to end the stream
    mock_pubsub.get_message = AsyncMock(side_effect=[
        {"type": "message", "data": b'{"job_id": "123", "step": "DONE", "status": "COMPLETED"}'}
    ])
    
    mock_client.pubsub.return_value = mock_pubsub
    mocker.patch("app.api.routes.get_async_redis_client", return_value=mock_client)
    return mock_pubsub
