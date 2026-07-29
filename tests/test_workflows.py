"""
Tests for ADK 2.0 Graph-Based Workflows.
"""

from personal_assistant.workflows import customer_refund_workflow, incident_response_workflow


def test_customer_refund_workflow_structure():
    """Verify customer_refund_workflow is built with ADK 2.0 graph edges."""
    assert customer_refund_workflow.name == "customer_refund_workflow"
    assert len(customer_refund_workflow.edges) > 0


def test_customer_refund_workflow_execution_eligible():
    """Simulate execution of eligible refund workflow."""
    state = {}
    from personal_assistant.workflows import (
        fetch_purchase_history,
        evaluate_eligibility_rule,
        issue_refund,
        compose_notification,
    )

    fetch_purchase_history(state)
    assert state["purchase_history"]["order_id"] == "ORD-2026-8842"

    eligible = evaluate_eligibility_rule(state)
    assert eligible is True

    if eligible:
        issue_refund(state)

    summary = compose_notification(state)
    assert "refunded" in summary.lower()
    assert state["status"] == "refunded"


def test_customer_refund_workflow_execution_ineligible():
    """Simulate execution of ineligible refund workflow."""
    state = {}
    from personal_assistant.workflows import (
        evaluate_eligibility_rule,
        reject_refund,
        compose_notification,
    )

    state["purchase_history"] = {"days_since_delivery": 45}
    eligible = evaluate_eligibility_rule(state)
    assert eligible is False

    if not eligible:
        reject_refund(state)

    summary = compose_notification(state)
    assert "rejected" in summary.lower()
    assert state["status"] == "rejected"


def test_incident_response_workflow_structure():
    """Verify incident_response_workflow structure."""
    assert incident_response_workflow.name == "incident_response_workflow"
    assert len(incident_response_workflow.edges) > 0
