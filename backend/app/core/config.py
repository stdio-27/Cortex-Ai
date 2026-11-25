from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://mongodb:27017"
    MONGODB_MAX_POOL_SIZE: int = 200
    MONGODB_DB_NAME: str = "research_copilot"
    REDIS_URI: str = "redis://redis:6379/0"
    REDIS_PUBSUB_URI: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_FAST_MODEL: str = "openai/gpt-oss-20b"
    TAVILY_API_KEY: str = ""
    MOCK_LLM_FOR_LOAD_TEST: bool = False
    
    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("REDIS_URI", "REDIS_PUBSUB_URI")
    @classmethod
    def secure_redis_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        parts = urlsplit(value)
        if parts.scheme != "rediss":
            return value
        # Both Celery and redis-py accept "required"; Celery's Redis result
        # backend also expects it to be explicit on TLS URLs.
        options = [
            (key, option)
            for key, option in parse_qsl(parts.query, keep_blank_values=True)
            if key not in {"ssl_cert_reqs", "ssl_check_hostname"}
        ]
        options.extend((("ssl_cert_reqs", "required"), ("ssl_check_hostname", "true")))
        return urlunsplit(parts._replace(query=urlencode(options)))

    @property
    def redis_pubsub_url(self) -> str:
        return self.REDIS_PUBSUB_URI or self.REDIS_URI

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
