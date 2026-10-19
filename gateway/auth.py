"""JWT creation and validation (HS256 only)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt


class AuthError(Exception):
    """The presented token is not acceptable."""


@dataclass(frozen=True)
class Identity:
    sub: str
    plan: str


def create_token(sub: str, plan: str, secret: str, ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    payload = {"sub": sub, "plan": plan, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str, valid_plans: set[str]) -> Identity:
    """Validate signature and expiry, and return the caller identity.

    The algorithm list is pinned to HS256, so tokens using 'none' or another
    algorithm are rejected instead of trusted.
    """
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid token") from exc

    sub = claims.get("sub")
    plan = claims.get("plan")
    if not isinstance(sub, str) or not sub:
        raise AuthError("invalid subject")
    if plan not in valid_plans or plan == "anonymous":
        raise AuthError("unknown plan")
    return Identity(sub=sub, plan=plan)
