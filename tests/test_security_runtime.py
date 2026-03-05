"""Runtime API security tests (auth + rate limiting)."""

from personal_assistant.shared.security import (
    _RATE_LIMIT_BUCKETS,
    check_api_key,
    check_rate_limit,
    parse_bearer_token,
    resolve_api_key,
)


def test_parse_bearer_token():
    assert parse_bearer_token("Bearer abc123") == "abc123"
    assert parse_bearer_token("bearer xyz") == "xyz"
    assert parse_bearer_token("Token abc") is None
    assert parse_bearer_token(None) is None


def test_resolve_api_key_priority():
    assert resolve_api_key(x_api_key="x-key", authorization_header="Bearer b-key") == "x-key"
    assert resolve_api_key(authorization_header="Bearer b-key") == "b-key"
    assert resolve_api_key(query_api_key="q-key") == "q-key"
    assert resolve_api_key() is None


def test_check_api_key_disabled_in_dev(monkeypatch):
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("APP_API_KEY", raising=False)
    allowed, reason = check_api_key(None)
    assert allowed
    assert reason == "auth disabled"


def test_check_api_key_enabled(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("APP_API_KEY", "token-1,token-2")

    allowed, _ = check_api_key("token-1")
    assert allowed

    allowed, reason = check_api_key("wrong-token")
    assert not allowed
    assert "invalid" in reason


def test_rate_limit_enforced():
    _RATE_LIMIT_BUCKETS.clear()
    key = "test-key"
    assert check_rate_limit(key, limit_per_minute=2, window_seconds=60)[0]
    assert check_rate_limit(key, limit_per_minute=2, window_seconds=60)[0]
    allowed, retry_after = check_rate_limit(key, limit_per_minute=2, window_seconds=60)
    assert not allowed
    assert retry_after >= 1
