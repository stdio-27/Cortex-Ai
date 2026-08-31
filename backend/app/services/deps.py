from app.services.interfaces import PubSubProvider, SearchProvider, LLMProvider

class Deps:
    def __init__(self, pubsub_service: PubSubProvider, tavily_service: SearchProvider, llm_service: LLMProvider):
        self.pubsub = pubsub_service
        self.tavily = tavily_service
        self.llm = llm_service
