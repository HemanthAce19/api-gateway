import base64
import json

import jwt
import pytest

from gateway.auth import AuthError, create_token, decode_token

SECRET = "a-secret-that-is-at-least-32-characters"
PLANS = {"anonymous", "free", "pro"}


def test_valid_token_returns_identity():
    token = create_token("alice", "pro", SECRET)
    identity = decode_token(token, SECRET, PLANS)
    assert (identity.sub, identity.plan) == ("alice", "pro")


def test_expired_token_rejected():
    token = create_token("alice", "free", SECRET, ttl_seconds=-10)
    with pytest.raises(AuthError, match="expired"):
        decode_token(token, SECRET, PLANS)


def test_wrong_signature_rejected():
    token = create_token("alice", "free", "some-other-secret-that-is-also-32-chars!")
    with pytest.raises(AuthError):
        decode_token(token, SECRET, PLANS)


def test_alg_none_rejected():
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'mallory', 'plan': 'pro', 'exp': 9999999999})}."
    with pytest.raises(AuthError):
        decode_token(forged, SECRET, PLANS)


def test_other_hmac_algorithm_rejected():
    token = jwt.encode({"sub": "a", "plan": "free", "exp": 9999999999}, SECRET, algorithm="HS512")
    with pytest.raises(AuthError):
        decode_token(token, SECRET, PLANS)


@pytest.mark.parametrize("plan", [None, "enterprise", "anonymous"])
def test_missing_or_unknown_plan_rejected(plan):
    claims = {"sub": "alice", "exp": 9999999999}
    if plan is not None:
        claims["plan"] = plan
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    with pytest.raises(AuthError, match="plan"):
        decode_token(token, SECRET, PLANS)


def test_missing_expiry_rejected():
    token = jwt.encode({"sub": "alice", "plan": "free"}, SECRET, algorithm="HS256")
    with pytest.raises(AuthError):
        decode_token(token, SECRET, PLANS)


def test_garbage_rejected():
    with pytest.raises(AuthError):
        decode_token("not.a.jwt", SECRET, PLANS)
