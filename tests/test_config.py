import pytest

from gateway.config import ConfigError, Settings


def test_short_secret_refused():
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        Settings.from_env({"JWT_SECRET": "short"})


def test_missing_secret_refused():
    with pytest.raises(ConfigError):
        Settings.from_env({})


def test_defaults_and_overrides():
    s = Settings.from_env({"JWT_SECRET": "x" * 32, "RL_FREE_CAPACITY": "3", "RL_FREE_PER_MINUTE": "6"})
    assert (s.plans["free"].capacity, s.plans["free"].per_minute) == (3, 6)
    assert s.plans["pro"].capacity == 100
    assert s.fail_mode == "open"


def test_bad_fail_mode_refused():
    with pytest.raises(ConfigError):
        Settings.from_env({"JWT_SECRET": "x" * 32, "RATE_LIMIT_FAIL_MODE": "maybe"})


def test_zero_limit_refused():
    with pytest.raises(ConfigError):
        Settings.from_env({"JWT_SECRET": "x" * 32, "RL_PRO_CAPACITY": "0"})
