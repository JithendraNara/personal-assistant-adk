"""
ADK 2.0 Graph-Based Workflows with Human-In-The-Loop (HITL) Interrupts.

Demonstrates deterministic, directed-graph workflow execution using ADK 2.0's `google.adk.workflow.Workflow`
and `google.adk.events.RequestInput` for Human-in-the-Loop approval checkpoints.
"""

from typing import Any

from google.adk.events import RequestInput
from google.adk.workflow import START, Workflow

# ─── 1. Customer Refund Processing Workflow (ADK 2.0 Graph + HITL) ───────────

def fetch_purchase_history(state: dict[str, Any]) -> str:
    """Step 1: Fast deterministic API/DB call to fetch user order history."""
    if "purchase_history" not in state:
        state["purchase_history"] = {
            "order_id": "ORD-2026-8842",
            "status": "delivered",
            "days_since_delivery": 12,
            "amount_usd": 149.99,
            "item": "Smart Noise-Canceling Headphones"
        }
    return "history_fetched"

def evaluate_eligibility_rule(state: dict[str, Any]) -> bool:
    """Step 2: Deterministic code rule check (no LLM required)."""
    history = state.get("purchase_history", {})
    days = history.get("days_since_delivery", 999)
    # Eligible if returned within 30 days
    is_eligible = days <= 30
    state["is_eligible"] = is_eligible
    return is_eligible

def check_high_value_approval(state: dict[str, Any]) -> dict[str, Any] | None:
    """HITL Checkpoint: High-value refund threshold (> $100 USD) requires operator approval."""
    history = state.get("purchase_history", {})
    amount = history.get("amount_usd", 0.0)

    # If user/operator already provided approval decision, proceed
    if "human_approval" in state:
        return None

    if amount > 100.0:
        req = RequestInput(
            interrupt_id="hitl_refund_approval",
            message=f"Refund amount (${amount:.2f}) exceeds $100.00 threshold. Operator approval required.",
            payload={"order_id": history.get("order_id"), "amount_usd": amount, "item": history.get("item")}
        )
        state["hitl_paused"] = True
        state["hitl_interrupt_id"] = req.interrupt_id
        state["hitl_message"] = req.message
        state["hitl_payload"] = req.payload
        return {
            "status": "paused",
            "interrupt_id": req.interrupt_id,
            "message": req.message,
            "payload": req.payload,
        }
    return None

def issue_refund(state: dict[str, Any]) -> str:
    """Step 3A: Programmatic refund processing via payment gateway."""
    state["refund_tx"] = "TX_REFUND_99412"
    state["status"] = "refunded"
    return "refund_issued"

def reject_refund(state: dict[str, Any]) -> str:
    """Step 3B: Mark request rejected when eligibility criteria fail or human rejects."""
    state["refund_tx"] = None
    state["status"] = "rejected"
    return "reject_refund"

def compose_notification(state: dict[str, Any]) -> str:
    """Step 4: Final status summary node."""
    status = state.get("status", "unknown")
    tx = state.get("refund_tx", "N/A")
    state["summary"] = f"Refund workflow complete. Status: {status}, Tx: {tx}"
    return state["summary"]

customer_refund_workflow = Workflow(
    name="customer_refund_workflow",
    description="ADK 2.0 deterministic directed-graph workflow for customer refund processing with HITL approval.",
    edges=[
        (START, fetch_purchase_history),
        (fetch_purchase_history, evaluate_eligibility_rule),
        (evaluate_eligibility_rule, {True: check_high_value_approval, False: reject_refund}),
        (check_high_value_approval, issue_refund),
        (issue_refund, compose_notification),
        (reject_refund, compose_notification),
    ]
)

# ─── 2. Incident Response Triage Workflow (ADK 2.0 Graph) ─────────────────────

def fetch_system_logs(state: dict[str, Any]) -> str:
    """Step 1: Collect system metrics and error logs."""
    if "system_metrics" not in state:
        state["system_metrics"] = {
            "service": "checkout-api",
            "error_rate_pct": 8.4,
            "primary_error": "504 Gateway Timeout on /v1/charge",
            "severity": "CRITICAL"
        }
    return "logs_fetched"

def evaluate_severity_rule(state: dict[str, Any]) -> bool:
    """Step 2: Deterministic severity threshold check."""
    metrics = state.get("system_metrics", {})
    is_critical = metrics.get("error_rate_pct", 0) > 5.0 or metrics.get("severity") == "CRITICAL"
    state["is_critical"] = is_critical
    return is_critical

def trigger_auto_failover(state: dict[str, Any]) -> str:
    """Step 3A: Trigger automatic Cloudflare failover endpoint."""
    state["remediation_action"] = "routed_traffic_to_standby_region"
    return "failover_triggered"

def log_minor_warning(state: dict[str, Any]) -> str:
    """Step 3B: Record low-severity alert."""
    state["remediation_action"] = "logged_warning_metrics"
    return "warning_logged"

incident_response_workflow = Workflow(
    name="incident_response_workflow",
    description="ADK 2.0 deterministic graph workflow for incident triage and automated failover.",
    edges=[
        (START, fetch_system_logs),
        (fetch_system_logs, evaluate_severity_rule),
        (evaluate_severity_rule, {True: trigger_auto_failover, False: log_minor_warning}),
    ]
)

WORKFLOW_REGISTRY: dict[str, Workflow] = {
    "customer_refund_workflow": customer_refund_workflow,
    "incident_response_workflow": incident_response_workflow,
}

def run_workflow_by_name(name: str, initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Execute an ADK 2.0 graph workflow deterministically over state.
    Handles HITL pauses (RequestInput) cleanly.
    """
    state = dict(initial_state or {})
    if name == "customer_refund_workflow":
        fetch_purchase_history(state)
        is_eligible = evaluate_eligibility_rule(state)
        if not is_eligible:
            reject_refund(state)
            compose_notification(state)
            return {"status": "completed", "state": state}

        # Check HITL approval
        hitl_pause = check_high_value_approval(state)
        if hitl_pause:
            return hitl_pause

        # If human rejected
        if state.get("human_approval") is False:
            reject_refund(state)
            compose_notification(state)
            return {"status": "completed", "state": state}

        issue_refund(state)
        compose_notification(state)
        return {"status": "completed", "state": state}

    elif name == "incident_response_workflow":
        fetch_system_logs(state)
        is_critical = evaluate_severity_rule(state)
        if is_critical:
            trigger_auto_failover(state)
        else:
            log_minor_warning(state)
        return {"status": "completed", "state": state}
    else:
        raise ValueError(f"Unknown workflow: {name}")

def resume_workflow_by_name(
    name: str,
    interrupt_id: str,
    approved: bool,
    current_state: dict[str, Any]
) -> dict[str, Any]:
    """Resume a paused ADK 2.0 workflow after human approval/rejection."""
    state = dict(current_state or {})
    state["human_approval"] = approved
    state.pop("hitl_paused", None)
    return run_workflow_by_name(name, state)
