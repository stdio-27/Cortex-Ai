import asyncio
import time
from unittest.mock import MagicMock
from app.agent.graph import agent_graph
from app.services.deps import Deps
from app.services.tavily_service import TavilyService
from app.services.llm_service import MockLLMService

class MockFlakyClient:
    def __init__(self, error_msg: str):
        self.error_msg = error_msg
    def search(self, query: str, **kwargs):
        raise Exception(self.error_msg)

async def test_retry():
    # Test 1: Transient/Retryable error (connection)
    print("=== TEST 1: RETRYABLE ERROR (Connection) ===")
    retryable_client = MockFlakyClient("Connection refused")
    tavily_service_1 = TavilyService(retryable_client)
    
    deps_1 = Deps(
        pubsub_service=MagicMock(),
        tavily_service=tavily_service_1,
        llm_service=MockLLMService()
    )

    initial_state_1 = {
        "job_id": "test_retry_job_1",
        "query": "Test query 1",
        "sub_topics": [],
        "search_results": [],
        "sanitized_content": "",
        "draft_report": "",
        "critique": "",
        "iteration_count": 0
    }

    try:
        final_state_1 = await agent_graph.ainvoke(
            initial_state_1,
            {
                "recursion_limit": 25,
                "configurable": {"deps": deps_1}
            }
        )
        print(f"Test 1 Search Results: {final_state_1.get('search_results')}")
    except Exception as e:
        print(f"Test 1 Graph execution failed with error: {e}")

    # Test 2: Non-retryable error (e.g. invalid API key)
    print("\n=== TEST 2: NON-RETRYABLE ERROR (Invalid API Key) ===")
    terminal_client = MockFlakyClient("Invalid API key")
    tavily_service_2 = TavilyService(terminal_client)
    
    deps_2 = Deps(
        pubsub_service=MagicMock(),
        tavily_service=tavily_service_2,
        llm_service=MockLLMService()
    )

    initial_state_2 = {
        "job_id": "test_retry_job_2",
        "query": "Test query 2",
        "sub_topics": [],
        "search_results": [],
        "sanitized_content": "",
        "draft_report": "",
        "critique": "",
        "iteration_count": 0
    }

    try:
        final_state_2 = await agent_graph.ainvoke(
            initial_state_2,
            {
                "recursion_limit": 25,
                "configurable": {"deps": deps_2}
            }
        )
        print(f"Test 2 Search Results: {final_state_2.get('search_results')}")
    except Exception as e:
        print(f"Test 2 Graph execution failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(test_retry())
