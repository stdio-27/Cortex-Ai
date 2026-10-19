from typing import List, Dict, Any

class TavilyService:
    def __init__(self, tavily_client):
        self.client = tavily_client

    def search(self, query: str) -> List[Dict[str, Any]]:
        response = self.client.search(query=query, search_depth="basic", max_results=3)
        return response.get("results", [])

class MockTavilyService:
    def __init__(self):
        # We use a simple counter to prove it retries
        self.counter = 0

    def search(self, query: str) -> List[Dict[str, Any]]:
        self.counter += 1
        print(f"MockTavilyService: Simulating transient failure (Call #{self.counter} for {query})")
        raise Exception("Connection timeout")
