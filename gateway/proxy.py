"""Forward a request to an upstream service and relay the response."""
from __future__ import annotations

import httpx
from fastapi import Request, Response

# Headers that describe a single connection and must not be forwarded.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    "content-encoding",
}


def build_upstream_headers(request: Request, user_id: str | None, plan: str) -> dict[str, str]:
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "authorization"
    }
    # Callers must not be able to claim an identity by sending these themselves.
    headers.pop("x-user-id", None)
    headers.pop("x-user-plan", None)
    if user_id:
        headers["X-User-Id"] = user_id
    headers["X-User-Plan"] = plan
    return headers


async def forward(
    client: httpx.AsyncClient, request: Request, upstream_base: str, user_id: str | None, plan: str
) -> Response:
    url = upstream_base + request.url.path
    upstream = await client.request(
        request.method,
        url,
        params=request.query_params,
        content=await request.body(),
        headers=build_upstream_headers(request, user_id, plan),
    )
    headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)
