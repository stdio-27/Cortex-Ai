from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Autonomous Research Copilot"
    MONGODB_URI: str = "mongodb://mongodb:27017"
    MONGODB_MAX_POOL_SIZE: int = 200
    MONGODB_DB_NAME: str = "research_copilot"
    REDIS_URI: str = "redis://redis:6379/0"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_FAST_MODEL: str = "openai/gpt-oss-20b"
    TAVILY_API_KEY: str = ""
    MOCK_LLM_FOR_LOAD_TEST: bool = False
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
