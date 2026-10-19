import asyncio

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from tests.conftest import bearer, make_settings


async def test_healthz_is_open(client):
    r = await client.get("/healthz")
    assert r.status_code == 200


async def test_proxies_to_upstream_and_sets_rate_limit_headers(client):
    r = await client.get("/orders", headers=bearer("alice", "free"))
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Limit"] == "10"
    assert r.headers["X-RateLimit-Remaining"] == "9"


async def test_upstream_sees_identity_but_not_the_token(client):
    r = await client.get("/orders/whoami", headers=bearer("alice", "pro"))
    assert r.json() == {"user": "alice", "plan": "pro", "authorization_header_received": False}


async def test_caller_cannot_spoof_identity_headers(client):
    headers = {**bearer("alice", "free"), "X-User-Id": "admin", "X-User-Plan": "pro"}
    r = await client.get("/orders/whoami", headers=headers)
    assert r.json()["user"] == "alice"
    assert r.json()["plan"] == "free"


async def test_post_body_and_status_are_relayed(client):
    r = await client.post("/orders", json={"item": "book", "quantity": 2}, headers=bearer("bob"))
    assert r.status_code == 201
    assert r.json()["owner"] == "bob"
    assert r.json()["quantity"] == 2


async def test_upstream_404_is_relayed(client):
    r = await client.get("/orders/999999", headers=bearer("alice"))
    assert r.status_code == 404


async def test_free_plan_blocked_after_capacity_with_retry_after(client):
    headers = bearer("alice", "free")
    codes = [(await client.get("/orders", headers=headers)).status_code for _ in range(12)]
    assert codes == [200] * 10 + [429] * 2
    blocked = await client.get("/orders", headers=headers)
    assert blocked.json()["error"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


async def test_pro_plan_has_higher_limit_than_free(client):
    free = [(await client.get("/orders", headers=bearer("f", "free"))).status_code for _ in range(15)]
    pro = [(await client.get("/orders", headers=bearer("p", "pro"))).status_code for _ in range(15)]
    assert free.count(429) == 5
    assert pro.count(429) == 0


async def test_users_do_not_share_a_bucket(client):
    for _ in range(10):
        await client.get("/orders", headers=bearer("alice"))
    assert (await client.get("/orders", headers=bearer("alice"))).status_code == 429
    assert (await client.get("/orders", headers=bearer("bob"))).status_code == 200


async def test_anonymous_limited_by_ip_with_lower_limit(client):
    codes = [(await client.get("/orders")).status_code for _ in range(7)]
    assert codes == [200] * 5 + [429] * 2


@pytest.mark.parametrize(
    "header",
    ["Bearer not.a.token", "Basic abc123", "Bearer", "garbage"],
)
async def test_bad_credentials_get_401_and_cost_no_tokens(client, header):
    r = await client.get("/orders", headers={"Authorization": header})
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert "X-RateLimit-Limit" not in r.headers


async def test_expired_token_gets_401(client):
    r = await client.get("/orders", headers=bearer("alice", "free", ttl=-5))
    assert r.status_code == 401
    assert "expired" in r.json()["detail"]


async def test_unknown_route_404(client):
    r = await client.get("/nothing-here", headers=bearer("alice"))
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


async def test_prefix_match_does_not_leak_to_similar_paths(client):
    r = await client.get("/orders-admin", headers=bearer("alice"))
    assert r.status_code == 404


async def test_concurrent_burst_through_gateway_admits_exactly_capacity(client):
    headers = bearer("alice", "free")
    responses = await asyncio.gather(*[client.get("/orders", headers=headers) for _ in range(100)])
    codes = [r.status_code for r in responses]
    assert codes.count(200) == 10
    assert codes.count(429) == 90


async def test_upstream_connection_failure_returns_502(redis):
    def boom(request):
        raise httpx.ConnectError("refused")

    from gateway.main import create_app

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    app = create_app(make_settings(), redis_client=redis, http_client=upstream)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gw") as c:
        r = await c.get("/orders", headers=bearer("alice"))
    assert r.status_code == 502
    assert r.json()["error"] == "bad_gateway"


async def test_upstream_timeout_returns_504(redis):
    def slow(request):
        raise httpx.ReadTimeout("too slow")

    from gateway.main import create_app

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(slow))
    app = create_app(make_settings(), redis_client=redis, http_client=upstream)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gw") as c:
        r = await c.get("/orders", headers=bearer("alice"))
    assert r.status_code == 504


class BrokenRedis:
    """Stands in for a Redis server that is down."""

    def register_script(self, _text):
        async def call(**_kwargs):
            raise RedisConnectionError("redis is down")

        return call


async def test_redis_down_fails_open_by_default(make_client):
    client = await make_client(make_settings(), redis_client=BrokenRedis())
    r = await client.get("/orders", headers=bearer("alice"))
    assert r.status_code == 200
    assert r.headers["X-RateLimit-Status"] == "degraded"


async def test_redis_down_fails_closed_when_configured(make_client):
    client = await make_client(make_settings(RATE_LIMIT_FAIL_MODE="closed"), redis_client=BrokenRedis())
    r = await client.get("/orders", headers=bearer("alice"))
    assert r.status_code == 503


async def test_demo_token_endpoint_disabled_by_default(client):
    r = await client.post("/auth/demo-token", json={"sub": "alice"})
    assert r.status_code in (404, 405)


async def test_demo_token_roundtrip_when_enabled(make_client):
    client = await make_client(make_settings(DEMO_MODE="true"))
    token = (await client.post("/auth/demo-token", json={"sub": "carol", "plan": "pro"})).json()
    r = await client.get("/orders/whoami", headers={"Authorization": f"Bearer {token['access_token']}"})
    assert r.json()["user"] == "carol"
    bad = await client.post("/auth/demo-token", json={"sub": "carol", "plan": "root"})
    assert bad.status_code == 400
