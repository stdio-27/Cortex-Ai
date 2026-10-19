import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock

# Must patch sys.modules before importing agent_runner because it imports them at module level
sys.modules['app.db.mongodb'] = MagicMock()
sys.modules['app.core.redis'] = MagicMock()

from app.agent.agent_runner import run_agent

async def test_end_to_end_real_runner():
    import app.db.mongodb as mongodb
    import app.core.redis as redis_mod
    
    # Setup Mongo mocks
    mock_collection = MagicMock()
    mock_collection.update_one = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value={"query": "Test real graph"})
    
    mongodb.db.client.__getitem__.return_value.__getitem__.return_value = mock_collection
    mongodb.connect_to_mongo = AsyncMock()
    mongodb.close_mongo_connection = AsyncMock()
    
    # Setup Redis mocks
    mock_redis = MagicMock()
    redis_mod.get_redis_client.return_value = mock_redis
    
    print("Executing agent_runner.run_agent()...")
    
    await run_agent("test_job_123")
    print("Execution finished.")

if __name__ == "__main__":
    asyncio.run(test_end_to_end_real_runner())
