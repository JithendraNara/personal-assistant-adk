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


def test_telemetry_status_endpoint(monkeypatch):
    serve = _load_serve(monkeypatch)
    with TestClient(serve.app) as client:
        unauth = client.get("/telemetry/status")
        assert unauth.status_code == 401

        auth = client.get("/telemetry/status", headers={"X-API-Key": "test-token"})
        assert auth.status_code == 200
        data = auth.json()
        assert "initialized" in data
        assert data["provider"] == "google.adk.telemetry"


def test_workflows_api_endpoints_and_hitl(monkeypatch):
    serve = _load_serve(monkeypatch)
    with TestClient(serve.app) as client:
        # List workflows
        res_list = client.get("/workflows", headers={"X-API-Key": "test-token"})
        assert res_list.status_code == 200
        names = [w["name"] for w in res_list.json()["workflows"]]
        assert "customer_refund_workflow" in names

        # Workflow introspection detail
        res_detail = client.get(
            "/workflows/customer_refund_workflow",
            headers={"X-API-Key": "test-token"},
        )
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["name"] == "customer_refund_workflow"
        assert len(detail["edges"]) > 0

        # Run low-value workflow -> completes
        res_run_low = client.post(
            "/workflows/customer_refund_workflow/run",
            headers={"X-API-Key": "test-token"},
            json={"state": {"purchase_history": {"days_since_delivery": 5, "amount_usd": 49.99}}},
        )
        assert res_run_low.status_code == 200
        run_data = res_run_low.json()
        assert run_data["status"] == "completed"
        assert run_data["state"]["status"] == "refunded"

        # Run high-value workflow -> HITL pauses
        res_run_high = client.post(
            "/workflows/customer_refund_workflow/run",
            headers={"X-API-Key": "test-token"},
            json={"state": {"purchase_history": {"days_since_delivery": 5, "amount_usd": 150.00}}},
        )
        assert res_run_high.status_code == 200
        pause_data = res_run_high.json()
        assert pause_data["status"] == "paused"
        assert pause_data["interrupt_id"] == "hitl_refund_approval"

        # Resume workflow with human approval
        res_resume = client.post(
            "/workflows/customer_refund_workflow/resume",
            headers={"X-API-Key": "test-token"},
            json={
                "interrupt_id": "hitl_refund_approval",
                "approved": True,
                "state": pause_data["payload"],
            },
        )
        assert res_resume.status_code == 200
        resume_data = res_resume.json()
        assert resume_data["status"] == "completed"
        assert resume_data["state"]["status"] == "refunded"
