"""Settings are read once from the environment into an immutable object."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

MIN_SECRET_LENGTH = 32

DEFAULT_PLANS: dict[str, tuple[int, int]] = {
    # plan: (capacity, tokens added per minute)
    "anonymous": (5, 5),
    "free": (10, 10),
    "pro": (100, 100),
}


class ConfigError(RuntimeError):
    """Raised when the gateway is configured unsafely or incorrectly."""


@dataclass(frozen=True)
class PlanLimit:
    capacity: int
    per_minute: int

    @property
    def rate_per_second(self) -> float:
        return self.per_minute / 60.0


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    redis_url: str = "redis://localhost:6379/0"
    routes_file: str = "routes.yaml"
    fail_mode: str = "open"  # "open" allows traffic when Redis is down, "closed" returns 503
    demo_mode: bool = False
    upstream_timeout: float = 5.0
    token_ttl_seconds: int = 3600
    plans: dict[str, PlanLimit] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)
        secret = env.get("JWT_SECRET", "")
        if len(secret) < MIN_SECRET_LENGTH:
            raise ConfigError(
                f"JWT_SECRET must be set and at least {MIN_SECRET_LENGTH} characters long"
            )
        fail_mode = env.get("RATE_LIMIT_FAIL_MODE", "open").lower()
        if fail_mode not in ("open", "closed"):
            raise ConfigError("RATE_LIMIT_FAIL_MODE must be 'open' or 'closed'")

        plans: dict[str, PlanLimit] = {}
        for name, (cap, per_min) in DEFAULT_PLANS.items():
            key = name.upper()
            plans[name] = PlanLimit(
                capacity=int(env.get(f"RL_{key}_CAPACITY", cap)),
                per_minute=int(env.get(f"RL_{key}_PER_MINUTE", per_min)),
            )
        for name, limit in plans.items():
            if limit.capacity < 1 or limit.per_minute < 1:
                raise ConfigError(f"Plan '{name}' needs a capacity and refill rate of at least 1")

        return cls(
            jwt_secret=secret,
            redis_url=env.get("REDIS_URL", cls.redis_url),
            routes_file=env.get("ROUTES_FILE", cls.routes_file),
            fail_mode=fail_mode,
            demo_mode=env.get("DEMO_MODE", "false").lower() == "true",
            upstream_timeout=float(env.get("UPSTREAM_TIMEOUT", cls.upstream_timeout)),
            token_ttl_seconds=int(env.get("TOKEN_TTL_SECONDS", cls.token_ttl_seconds)),
            plans=plans,
        )
