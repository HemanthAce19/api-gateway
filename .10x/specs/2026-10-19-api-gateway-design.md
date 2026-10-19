# Rate-Limited API Gateway: Design Spec

Date: 2026-10-19 | Owner: Hemanth Pandiyaraj (HemanthAce19) | Slug: api-gateway

## Goal
A small, production-shaped API gateway that authenticates callers with JWT, rate limits them
with an atomic Redis token bucket, and proxies allowed traffic to an upstream service. The repo
must be demoable in one command and explainable in an interview.

## Decisions made with the user
- Upstream: a demo "orders" service lives in the repo; routes are set in `routes.yaml`.
- Rate limit key: per authenticated user with plan tiers; anonymous callers fall back to per-IP.
- Stack: FastAPI, async Redis (redis-py), httpx for proxying, Lua script for the bucket, pytest.

## Request flow
1. Authenticate: Bearer JWT. No token = anonymous. Invalid or expired token = 401.
2. Rate limit: key is `user:<sub>` or `ip:<addr>`. Denied = 429 with `Retry-After`.
   Every response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`.
3. Proxy: longest-prefix match on `routes.yaml`, forward with httpx, relay status, headers, body
   (buffered). Unknown path = 404. Upstream connect error = 502. Upstream timeout = 504.
4. Log: one structured line per request (user, plan, route, status, latency_ms).

## Token bucket
Continuous refill, not fixed windows. State is a Redis hash `rl:<key>` with `tokens` and `ts`.
A single Lua script refills, checks and decrements atomically and uses Redis `TIME` as the clock,
so multiple gateway instances cannot race and clock drift does not matter. TTL is 2x full-refill time.

| Plan | Capacity | Refill per minute |
|---|---|---|
| anonymous | 5 | 5 |
| free | 10 | 10 |
| pro | 100 | 100 |

Values are overridable with env vars `RL_<PLAN>_CAPACITY` and `RL_<PLAN>_PER_MINUTE`.

## Defaults chosen for sections not discussed (review these)
- JWT: HS256 only, secret from `JWT_SECRET` (min 32 chars, app refuses to start otherwise).
  Required claims: `sub`, `plan`, `exp`. Unknown plan = 401. `alg: none` rejected.
- Token issuing: `scripts/make_token.py`, plus `POST /auth/demo-token` only when `DEMO_MODE=true`.
- Upstream headers: `Authorization` is stripped; `X-User-Id` and `X-User-Plan` are added.
  Hop-by-hop headers are dropped.
- Client IP: `request.client.host`. `X-Forwarded-For` is ignored (spoofable); documented in README.
- Redis failure: configurable `RATE_LIMIT_FAIL_MODE`, default `open` (allow, log error, mark
  `X-RateLimit-Status: degraded`). `closed` returns 503.
- Health: `GET /healthz` is unauthenticated and not rate limited.

## Out of scope (YAGNI)
Per-route limits, API key management, metrics dashboards, sliding-log limiter, multi-upstream load
balancing, TLS termination.

## Testing
pytest with pytest-asyncio. Unit tests for JWT and the limiter, gateway tests with the demo app as
an in-process ASGI upstream, and a 200-concurrent-request test asserting exactly `capacity`
requests pass. A real-Redis test runs when `REDIS_URL` is set (CI sets it).

## Demo plan
`docker compose up` then `scripts/demo.sh`: unprotected service vs gateway, 401 on bad token,
free vs pro limits, 429 + Retry-After, then `scripts/load_test.py` with 200 concurrent requests.
