from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    job_id: str
    query: str
    sub_topics: List[str]
    search_results: Annotated[List[dict], operator.add]
    sanitized_content: str
    draft_report: str
    critique: str
    iteration_count: int
