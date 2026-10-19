import os
from pathlib import Path

import fakeredis
import httpx
import pytest_asyncio
from redis.asyncio import Redis

from demo_service.main import app as demo_app
from gateway.auth import create_token
from gateway.config import Settings
from gateway.main import create_app

ROOT = Path(__file__).resolve().parent.parent
SECRET = "test-secret-that-is-definitely-32-chars-long"


def make_settings(**overrides) -> Settings:
    env = {"JWT_SECRET": SECRET, "ROUTES_FILE": str(ROOT / "routes.yaml")}
    env.update(overrides)
    return Settings.from_env(env)


@pytest_asyncio.fixture
async def redis():
    """Real Redis when REDIS_URL is set (CI), otherwise an in-memory Redis with Lua support."""
    url = os.environ.get("REDIS_URL")
    if url:
        client = Redis.from_url(url, decode_responses=True, max_connections=500)
    else:
        client = fakeredis.FakeAsyncRedis(decode_responses=True, max_connections=500)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def make_client(redis):
    """Factory returning a client wired to a gateway whose upstream is the in-process demo app."""
    opened: list[httpx.AsyncClient] = []

    async def _make(settings: Settings | None = None, redis_client=None) -> httpx.AsyncClient:
        upstream = httpx.AsyncClient(transport=httpx.ASGITransport(app=demo_app))
        gateway = create_app(
            settings or make_settings(), redis_client=redis_client or redis, http_client=upstream
        )
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=gateway), base_url="http://gateway"
        )
        opened.extend([client, upstream])
        return client

    yield _make
    for c in opened:
        await c.aclose()


@pytest_asyncio.fixture
async def client(make_client):
    return await make_client()


def bearer(sub: str, plan: str = "free", ttl: int = 3600) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(sub, plan, SECRET, ttl)}"}
