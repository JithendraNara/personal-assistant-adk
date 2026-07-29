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


def test_workflows_api_endpoints(monkeypatch):
    serve = _load_serve(monkeypatch)
    with TestClient(serve.app) as client:
        # Unauthenticated request fails
        res_unauth = client.get("/workflows")
        assert res_unauth.status_code == 401

        # Authenticated list workflows
        res_list = client.get("/workflows", headers={"X-API-Key": "test-token"})
        assert res_list.status_code == 200
        wf_data = res_list.json()
        assert "workflows" in wf_data
        names = [w["name"] for w in wf_data["workflows"]]
        assert "customer_refund_workflow" in names

        # Execute refund workflow via API
        res_run = client.post(
            "/workflows/customer_refund_workflow/run",
            headers={"X-API-Key": "test-token"},
            json={"state": {"purchase_history": {"days_since_delivery": 5}}},
        )
        assert res_run.status_code == 200
        run_data = res_run.json()
        assert run_data["status"] == "completed"
        assert run_data["state"]["status"] == "refunded"

