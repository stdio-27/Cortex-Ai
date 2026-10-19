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

async def run_job(job_id: str, deps: Deps):
    initial_state = {
        "job_id": job_id,
        "query": "Concurrent query",
        "sub_topics": [],
        "search_results": [],
        "sanitized_content": "",
        "draft_report": "",
        "critique": "",
        "iteration_count": 0
    }
    
    print(f"Starting {job_id}...")
    final_state = await agent_graph.ainvoke(
        initial_state,
        {
            "recursion_limit": 25,
            "configurable": {"deps": deps}
        }
    )
    print(f"Finished {job_id}. Search Results: {final_state.get('search_results')}")

async def test_concurrent_retries():
    # Use real TavilyService with a MockClient that throws connection errors
    retryable_client = MockFlakyClient("Connection refused")
    tavily_service = TavilyService(retryable_client)
    
    deps = Deps(
        pubsub_service=MagicMock(),
        tavily_service=tavily_service,
        llm_service=MockLLMService()
    )

    print("=== TEST CONCURRENT RETRIES ===")
    # Run two identical jobs concurrently sharing the same TavilyService instance
    await asyncio.gather(
        run_job("job_A", deps),
        run_job("job_B", deps)
    )

if __name__ == "__main__":
    asyncio.run(test_concurrent_retries())
