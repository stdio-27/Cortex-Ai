from app.services.interfaces import SearchProvider, LLMProvider
from app.services.pubsub_service import PubSubService

class Deps:
    def __init__(self, pubsub_service: PubSubService, tavily_service: SearchProvider, llm_service: LLMProvider):
        self.pubsub = pubsub_service
        self.tavily = tavily_service
        self.llm = llm_service
