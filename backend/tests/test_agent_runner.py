import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.agent.agent_runner import run_agent

@pytest.mark.asyncio
@patch("app.agent.agent_runner.db")
@patch("app.core.redis.get_redis_client")
@patch("app.agent.agent_runner.MongoDBSaver")
@patch("app.agent.agent_runner.settings")
async def test_run_agent(mock_settings, mock_mongo_saver, mock_get_redis, mock_db):
    from langgraph.checkpoint.memory import InMemorySaver
    mock_settings.MOCK_LLM_FOR_LOAD_TEST = True
    mock_settings.MONGODB_DB_NAME = "test_db"
    # Setup Mongo mocks
    mock_collection = MagicMock()
    mock_collection.update_one = MagicMock()
    mock_collection.find_one = MagicMock(return_value={"query": "Test real graph", "_id": "123"})
    mock_db.sync_client.__getitem__.return_value.__getitem__.return_value = mock_collection
    
    mock_mongo_saver.return_value = InMemorySaver()
    
    # Setup Redis mocks
    mock_redis = MagicMock()
    mock_get_redis.return_value = mock_redis
    
    print("Executing agent_runner.run_agent()...")
    await run_agent("test_job_123")
    print("Execution finished.")


@pytest.mark.asyncio
@patch("app.agent.agent_runner.db")
async def test_run_agent_propagates_errors(mock_db):
    mock_collection = MagicMock()
    mock_collection.find_one = MagicMock(side_effect=RuntimeError("boom"))
    mock_db.sync_client.__getitem__.return_value.__getitem__.return_value = mock_collection

    with pytest.raises(RuntimeError, match="boom"):
        await run_agent("test_job_err")
