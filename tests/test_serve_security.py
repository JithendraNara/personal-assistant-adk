"""Serve.py security behavior tests."""

import importlib

from fastapi.testclient import TestClient


def _load_serve(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("APP_API_KEY", "test-token")
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy")
    import serve

    return importlib.reload(serve)


def test_health_is_open_but_config_requires_auth(monkeypatch):
    serve = _load_serve(monkeypatch)
    with TestClient(serve.app) as client:
        health = client.get("/health")
        assert health.status_code == 200

        unauthorized = client.get("/config")
        assert unauthorized.status_code == 401

        authorized = client.get("/config", headers={"X-API-Key": "test-token"})
        assert authorized.status_code == 200


def test_config_accepts_bearer_token(monkeypatch):
    serve = _load_serve(monkeypatch)
    with TestClient(serve.app) as client:
        res = client.get("/config", headers={"Authorization": "Bearer test-token"})
        assert res.status_code == 200


def test_mission_control_routes_require_auth_for_data(monkeypatch):
    serve = _load_serve(monkeypatch)
    with TestClient(serve.app) as client:
        dashboard = client.get("/mission-control")
        sessions_page = client.get("/mission-control/sessions")
        agents_page = client.get("/mission-control/agents")
        console_page = client.get("/mission-control/console")
        assert dashboard.status_code == 200
        assert sessions_page.status_code == 200
        assert agents_page.status_code == 200
        assert console_page.status_code == 200

        unauthorized = client.get("/api/mission-control/snapshot")
        assert unauthorized.status_code == 401

        authorized = client.get(
            "/api/mission-control/snapshot",
            headers={"X-API-Key": "test-token"},
        )
        assert authorized.status_code == 200
        payload = authorized.json()
        assert "overview" in payload
        assert "runtime" in payload
