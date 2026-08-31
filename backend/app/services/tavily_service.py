from typing import List, Dict, Any

class TavilyService:
    def __init__(self, tavily_client):
        self.client = tavily_client

    def search(self, query: str, search_depth: str = "basic", max_results: int = 3) -> List[Dict[str, Any]]:
        try:
            response = self.client.search(query=query, search_depth=search_depth, max_results=max_results)
            return response.get("results", [])
        except Exception as e:
            print(f"Search failed for {query}: {e}")
            return []

class MockTavilyService:
    def search(self, query: str, search_depth: str = "basic", max_results: int = 3) -> List[Dict[str, Any]]:
        return [{"url": "http://mock.url", "content": "Mock search result content."}]
