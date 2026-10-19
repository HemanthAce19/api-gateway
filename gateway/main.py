"""Gateway application: authenticate, rate limit, then proxy.

Run with:  uvicorn gateway.main:create_app --factory
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError

from gateway.auth import AuthError, create_token, decode_token
from gateway.config import Settings
from gateway.proxy import forward
from gateway.ratelimit import TokenBucketLimiter
from gateway.routes import RouteTable

logger = logging.getLogger("gateway")

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


def _error(status: int, error: str, detail: str, headers: dict[str, str] | None = None):
    return JSONResponse({"error": error, "detail": detail}, status_code=status, headers=headers)


class TokenRequest(BaseModel):
    sub: str
    plan: str = "free"


def create_app(
    settings: Settings | None = None,
    redis_client: Redis | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    """Build the app. Clients can be injected (tests); otherwise they are created at startup."""
    settings = settings or Settings.from_env()
    routes = RouteTable.from_file(settings.routes_file)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned: list = []
        if app.state.redis is None:
            app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
            owned.append(app.state.redis)
        if app.state.limiter is None:
            app.state.limiter = TokenBucketLimiter(app.state.redis)
        if app.state.http is None:
            app.state.http = httpx.AsyncClient(timeout=settings.upstream_timeout)
            owned.append(app.state.http)
        yield
        for client in owned:
            await (client.aclose() if hasattr(client, "aclose") else client.close())

    app = FastAPI(title="API Gateway", lifespan=lifespan)
    app.state.settings = settings
    app.state.redis = redis_client
    app.state.http = http_client
    app.state.limiter = TokenBucketLimiter(redis_client) if redis_client is not None else None

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    if settings.demo_mode:

        @app.post("/auth/demo-token")
        async def demo_token(body: TokenRequest):
            if body.plan not in settings.plans or body.plan == "anonymous":
                return _error(400, "bad_request", "plan must be 'free' or 'pro'")
            token = create_token(body.sub, body.plan, settings.jwt_secret, settings.token_ttl_seconds)
            return {"access_token": token, "token_type": "bearer"}

    @app.api_route("/{path:path}", methods=METHODS)
    async def gateway(request: Request, path: str) -> Response:
        started = time.perf_counter()
        identity = None
        extra_headers: dict[str, str] = {}

        def finish(response: Response) -> Response:
            for k, v in extra_headers.items():
                response.headers[k] = v
            logger.info(
                "request user=%s plan=%s method=%s path=%s status=%s latency_ms=%.1f",
                identity.sub if identity else "-",
                identity.plan if identity else "anonymous",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - started) * 1000,
            )
            return response

        # 1. Authenticate
        auth_header = request.headers.get("authorization")
        if auth_header:
            scheme, _, token = auth_header.partition(" ")
            try:
                if scheme.lower() != "bearer" or not token:
                    raise AuthError("expected 'Authorization: Bearer <token>'")
                identity = decode_token(token, settings.jwt_secret, set(settings.plans))
            except AuthError as exc:
                return finish(_error(401, "unauthorized", str(exc), {"WWW-Authenticate": "Bearer"}))

        plan = identity.plan if identity else "anonymous"
        client_host = request.client.host if request.client else "unknown"
        bucket_key = f"user:{identity.sub}" if identity else f"ip:{client_host}"
        limit = settings.plans[plan]

        # 2. Rate limit
        try:
            decision = await request.app.state.limiter.acquire(
                bucket_key, limit.capacity, limit.per_minute
            )
        except (RedisError, OSError):
            logger.exception("rate limiter unavailable (fail_mode=%s)", settings.fail_mode)
            if settings.fail_mode == "closed":
                return finish(_error(503, "unavailable", "rate limiter unavailable"))
            extra_headers["X-RateLimit-Status"] = "degraded"
        else:
            extra_headers["X-RateLimit-Limit"] = str(decision.limit)
            extra_headers["X-RateLimit-Remaining"] = str(decision.remaining)
            if not decision.allowed:
                extra_headers["Retry-After"] = str(decision.retry_after)
                return finish(_error(429, "rate_limited", "too many requests"))

        # 3. Proxy
        route = routes.match(request.url.path)
        if route is None:
            return finish(_error(404, "not_found", "no route for this path"))
        try:
            response = await forward(
                request.app.state.http,
                request,
                route.upstream,
                identity.sub if identity else None,
                plan,
            )
        except httpx.TimeoutException:
            return finish(_error(504, "gateway_timeout", "upstream timed out"))
        except httpx.HTTPError:
            return finish(_error(502, "bad_gateway", "upstream unavailable"))
        return finish(response)

    return app
