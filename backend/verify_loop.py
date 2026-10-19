import asyncio
import time
from unittest.mock import MagicMock
from app.agent.graph import agent_graph
from app.services.deps import Deps
from app.services.tavily_service import MockTavilyService
from app.services.llm_service import MockLLMService

class AlwaysFailMockLLMService(MockLLMService):
    def critique_report(self, query: str, draft_report: str) -> str:
        print(f"--> MOCK CRITIQUE RUNNING... returning 'NEEDS IMPROVEMENT'")
        return "NEEDS IMPROVEMENT"

async def test_loop():
    deps = Deps(
        pubsub_service=MagicMock(),
        tavily_service=MockTavilyService(),
        llm_service=AlwaysFailMockLLMService()
    )

    initial_state = {
        "job_id": "test_loop_job",
        "query": "Test critique loop",
        "sub_topics": [],
        "search_results": [],
        "sanitized_content": "",
        "draft_report": "",
        "critique": "",
        "iteration_count": 0
    }

    print("Starting loop test...")
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
    print(f"Final iteration count: {final_state.get('iteration_count')}")
    print(f"Final critique: {final_state.get('critique')}")

if __name__ == "__main__":
    asyncio.run(test_loop())
