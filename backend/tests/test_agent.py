import pytest
from app.agent.nodes import planner_node, sanitization_node, critique_node, settings
from app.agent.graph import should_continue
from langgraph.graph import END

@pytest.fixture(autouse=True)
def mock_llm_mode(mocker):
    # Force mock mode to avoid hitting real LLMs
    mocker.patch.object(settings, "MOCK_LLM_FOR_LOAD_TEST", True)
    
    # No longer need to mock redis_client.publish globally
    # since we use MagicMock via dependency injection

from unittest.mock import MagicMock

class MockTavilyService:
    def search(self, query: str):
        return [{"url": "http://mock.url", "content": "Mock search result content."}]

class MockLLMService:
    def generate_sub_topics(self, query: str):
        return ["Mock topic 1", "Mock topic 2", "Mock topic 3"]

    def sanitize_search_results(self, raw_results):
        return "Mock sanitized content based on search results."

    def synthesize_report(self, query: str, sanitized_content: str, critique: str):
        return f"# Mock Report for {query}\n\nThis is a mocked report generated for load testing purposes. It bypasses the real LLM."

    def critique_report(self, query: str, draft_report: str):
        return "APPROVED"

class MockDeps:
    def __init__(self):
        self.pubsub = MagicMock()
        self.tavily = MockTavilyService()
        self.llm = MockLLMService()

@pytest.fixture
def mock_config():
    return {"configurable": {"deps": MockDeps()}}

def test_planner_node(mock_config):
    state = {"job_id": "123", "query": "test query"}
    result = planner_node(state, mock_config)
    
    assert "sub_topics" in result
    assert isinstance(result["sub_topics"], list)
    assert len(result["sub_topics"]) == 3

def test_sanitization_node(mock_config):
    state = {
        "job_id": "123", 
        "search_results": [{"topic": "test", "results": [{"content": "dirty data"}]}]
    }
    result = sanitization_node(state, mock_config)
    
    assert "sanitized_content" in result
    assert "Mock sanitized content" in result["sanitized_content"]

def test_critique_node(mock_config):
    state = {"job_id": "123", "query": "test", "draft_report": "draft"}
    result = critique_node(state, mock_config)
    
    assert "critique" in result
    assert result["critique"] == "APPROVED"

def test_circuit_breaker_approved():
    state = {"critique": "APPROVED", "iteration_count": 1}
    result = should_continue(state)
    assert result == END

def test_circuit_breaker_max_iterations():
    state = {"critique": "NEEDS IMPROVEMENT", "iteration_count": 2}
    result = should_continue(state)
    assert result == END

def test_circuit_breaker_continue():
    state = {"critique": "NEEDS IMPROVEMENT", "iteration_count": 1}
    result = should_continue(state)
    assert result == "synthesizer"
