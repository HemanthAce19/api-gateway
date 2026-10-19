"""Token bucket rate limiter backed by an atomic Redis Lua script."""
from __future__ import annotations

import math
from importlib import resources
from typing import NamedTuple

from redis.asyncio import Redis


class Decision(NamedTuple):
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # whole seconds, 0 when allowed


def _load_script() -> str:
    return resources.files("gateway").joinpath("token_bucket.lua").read_text(encoding="utf-8")


class TokenBucketLimiter:
    def __init__(self, redis: Redis, prefix: str = "rl:") -> None:
        self._prefix = prefix
        self._script = redis.register_script(_load_script())

    async def acquire(self, key: str, capacity: int, per_minute: int, cost: int = 1) -> Decision:
        """Try to take `cost` tokens from the bucket for `key`."""
        rate_per_second = per_minute / 60.0
        allowed, tokens, retry_after = await self._script(
            keys=[self._prefix + key],
            args=[capacity, rate_per_second, cost],
        )
        remaining = max(0, math.floor(float(tokens)))
        wait = math.ceil(float(retry_after)) if not int(allowed) else 0
        return Decision(
            allowed=bool(int(allowed)),
            limit=capacity,
            remaining=remaining,
            retry_after=wait,
        )
