import asyncio
import sys
import time
from pathlib import Path

# Run this inside the container directly:
# docker exec cortex-web-1 python verify_concurrency.py

from unittest.mock import MagicMock
from app.agent.graph import agent_graph
from app.services.deps import Deps
from app.services.tavily_service import MockTavilyService
from app.services.llm_service import MockLLMService

class SlowMockTavilyService(MockTavilyService):
    def search(self, query: str):
        # Simulate a slow API call taking exactly 2 seconds
        time.sleep(2)
        return [{"url": "http://mock.url", "content": f"Mock result for {query}"}]

async def test_concurrency():
    # Setup deps with the slow mock search service
    deps = Deps(
        pubsub_service=MagicMock(),
        tavily_service=SlowMockTavilyService(),
        llm_service=MockLLMService()
    )

    initial_state = {
        "job_id": "test_concurrency_job",
        "query": "Test query with 3 subtopics",
        "sub_topics": [],
        "search_results": [],
        "sanitized_content": "",
        "draft_report": "",
        "critique": "",
        "iteration_count": 0
    }

    start_time = time.time()
    # Run pipeline
    final_state = await agent_graph.ainvoke(
        initial_state,
        {
            "recursion_limit": 25,
            "configurable": {"deps": deps}
        }
    )
    end_time = time.time()

    elapsed = end_time - start_time
    print(f"Total time taken: {elapsed:.2f} seconds")
    print(f"Number of subtopics searched: {len(final_state['search_results'])}")

if __name__ == "__main__":
    asyncio.run(test_concurrency())
