import pytest
from app.agent.nodes import planner_node, sanitization_node, critique_node, settings
from app.agent.graph import should_continue
from langgraph.graph import END

@pytest.fixture(autouse=True)
def mock_llm_mode(mocker):
    # Force mock mode to avoid hitting real LLMs
    mocker.patch.object(settings, "MOCK_LLM_FOR_LOAD_TEST", True)
    
    # Also mock Redis publish to avoid connection errors during testing
    mocker.patch("app.agent.nodes.redis_client.publish")

def test_planner_node():
    state = {"job_id": "123", "query": "test query", "iteration_count": 0}
    result = planner_node(state)
    
    assert "sub_topics" in result
    assert isinstance(result["sub_topics"], list)
    assert len(result["sub_topics"]) == 3
    assert result["iteration_count"] == 0

def test_sanitization_node():
    state = {
        "job_id": "123", 
        "search_results": [{"topic": "test", "results": [{"content": "dirty data"}]}]
    }
    result = sanitization_node(state)
    
    assert "sanitized_content" in result
    assert "Mock sanitized content" in result["sanitized_content"]

def test_critique_node():
    state = {"job_id": "123", "query": "test", "draft_report": "draft"}
    result = critique_node(state)
    
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
