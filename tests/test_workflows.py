"""
Tests for ADK 2.0 Graph-Based Workflows.
"""

from personal_assistant.workflows import (
    customer_refund_workflow,
    incident_response_workflow,
    resume_workflow_by_name,
    run_workflow_by_name,
)


def test_customer_refund_workflow_structure():
    """Verify customer_refund_workflow is built with ADK 2.0 graph edges."""
    assert customer_refund_workflow.name == "customer_refund_workflow"
    assert len(customer_refund_workflow.edges) > 0


def test_customer_refund_workflow_execution_low_value():
    """Simulate execution of low-value eligible refund workflow (< $100, no HITL needed)."""
    state = {"purchase_history": {"order_id": "O1", "days_since_delivery": 5, "amount_usd": 49.99}}
    res = run_workflow_by_name("customer_refund_workflow", state)
    assert res["status"] == "completed"
    assert res["state"]["status"] == "refunded"


def test_customer_refund_workflow_hitl_pause_and_resume_approved():
    """Verify high-value refund (> $100) triggers HITL pause and resumes upon operator approval."""
    state = {"purchase_history": {"order_id": "O2", "days_since_delivery": 10, "amount_usd": 199.99}}
    pause_res = run_workflow_by_name("customer_refund_workflow", state)

    # HITL interrupt pause verification
    assert pause_res["status"] == "paused"
    assert pause_res["interrupt_id"] == "hitl_refund_approval"
    assert "Operator approval required" in pause_res["message"]

    # Resume with approval
    resume_res = resume_workflow_by_name(
        name="customer_refund_workflow",
        interrupt_id="hitl_refund_approval",
        approved=True,
        current_state=state,
    )
    assert resume_res["status"] == "completed"
    assert resume_res["state"]["status"] == "refunded"
    assert resume_res["state"]["human_approval"] is True


def test_customer_refund_workflow_hitl_pause_and_resume_rejected():
    """Verify high-value refund (> $100) triggers HITL pause and rejects upon operator rejection."""
    state = {"purchase_history": {"order_id": "O3", "days_since_delivery": 10, "amount_usd": 250.00}}
    pause_res = run_workflow_by_name("customer_refund_workflow", state)
    assert pause_res["status"] == "paused"

    # Resume with rejection
    resume_res = resume_workflow_by_name(
        name="customer_refund_workflow",
        interrupt_id="hitl_refund_approval",
        approved=False,
        current_state=state,
    )
    assert resume_res["status"] == "completed"
    assert resume_res["state"]["status"] == "rejected"
    assert resume_res["state"]["human_approval"] is False


def test_incident_response_workflow_structure():
    """Verify incident_response_workflow structure and execution."""
    assert incident_response_workflow.name == "incident_response_workflow"
    assert len(incident_response_workflow.edges) > 0

    res = run_workflow_by_name("incident_response_workflow", {})
    assert res["status"] == "completed"
    assert res["state"]["remediation_action"] == "routed_traffic_to_standby_region"
