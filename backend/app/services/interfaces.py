from typing import Protocol, List, Dict, Any

class SearchProvider(Protocol):
    def search(self, query: str) -> List[Dict[str, Any]]:
        ...

class LLMProvider(Protocol):
    def generate_sub_topics(self, query: str) -> List[str]:
        ...

    def sanitize_search_results(self, raw_results: List[dict]) -> str:
        ...

    def synthesize_report(self, query: str, sanitized_content: str, critique: str) -> str:
        ...

    def critique_report(self, query: str, draft_report: str) -> str:
        ...
