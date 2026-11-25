import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app


def test_cloud_settings_normalize_origins_and_redis_tls():
    settings = Settings(
        _env_file=None,
        REDIS_URI="rediss://redis.example.com:6380/0?ssl_cert_reqs=none&ssl_check_hostname=false&socket_timeout=4",
        REDIS_PUBSUB_URI=" ",
        CORS_ORIGINS="https://cortex.example.com/, , http://localhost:5173",
    )
    assert settings.cors_origins == ["https://cortex.example.com", "http://localhost:5173"]
    assert settings.redis_pubsub_url == (
        "rediss://redis.example.com:6380/0?socket_timeout=4&ssl_cert_reqs=required&ssl_check_hostname=true"
    )
    separate = Settings(
        _env_file=None,
        REDIS_URI="redis://redis:6379/0",
        REDIS_PUBSUB_URI="redis://redis:6379/1",
    )
    assert separate.redis_pubsub_url == "redis://redis:6379/1"


@pytest.mark.asyncio
async def test_render_liveness():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
