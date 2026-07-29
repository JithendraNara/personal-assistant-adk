"""
ADK 2.0 Graph-Based Workflows.

Demonstrates deterministic, directed-graph workflow execution using ADK 2.0's `google.adk.workflow.Workflow`.
Separates application execution routing from open-ended language model calls.
"""

from typing import Any, Dict
from google.adk.workflow import Workflow, START

# ─── 1. Customer Refund Processing Workflow (ADK 2.0 Graph) ───────────────────

def fetch_purchase_history(state: Dict[str, Any]) -> str:
    """Step 1: Fast deterministic API/DB call to fetch user order history."""
    state["purchase_history"] = {
        "order_id": "ORD-2026-8842",
        "status": "delivered",
        "days_since_delivery": 12,
        "amount_usd": 149.99,
        "item": "Smart Noise-Canceling Headphones"
    }
    return "history_fetched"

def evaluate_eligibility_rule(state: Dict[str, Any]) -> bool:
    """Step 2: Deterministic code rule check (no LLM required)."""
    history = state.get("purchase_history", {})
    days = history.get("days_since_delivery", 999)
    # Eligible if returned within 30 days
    is_eligible = days <= 30
    state["is_eligible"] = is_eligible
    return is_eligible

def issue_refund(state: Dict[str, Any]) -> str:
    """Step 3A: Programmatic refund processing via payment gateway."""
    state["refund_tx"] = "TX_REFUND_99412"
    state["status"] = "refunded"
    return "refund_issued"

def reject_refund(state: Dict[str, Any]) -> str:
    """Step 3B: Mark request rejected when eligibility criteria fail."""
    state["refund_tx"] = None
    state["status"] = "rejected"
    return "refund_rejected"

def compose_notification(state: Dict[str, Any]) -> str:
    """Step 4: Final status summary node."""
    status = state.get("status", "unknown")
    tx = state.get("refund_tx", "N/A")
    state["summary"] = f"Refund workflow complete. Status: {status}, Tx: {tx}"
    return state["summary"]

customer_refund_workflow = Workflow(
    name="customer_refund_workflow",
    description="ADK 2.0 deterministic directed-graph workflow for customer refund processing.",
    edges=[
        (START, fetch_purchase_history),
        (fetch_purchase_history, evaluate_eligibility_rule),
        (evaluate_eligibility_rule, {True: issue_refund, False: reject_refund}),
        (issue_refund, compose_notification),
        (reject_refund, compose_notification),
    ]
)

# ─── 2. Incident Response Triage Workflow (ADK 2.0 Graph) ─────────────────────

def fetch_system_logs(state: Dict[str, Any]) -> str:
    """Step 1: Collect system metrics and error logs."""
    state["system_metrics"] = {
        "service": "checkout-api",
        "error_rate_pct": 8.4,
        "primary_error": "504 Gateway Timeout on /v1/charge",
        "severity": "CRITICAL"
    }
    return "logs_fetched"

def evaluate_severity_rule(state: Dict[str, Any]) -> bool:
    """Step 2: Deterministic severity threshold check."""
    metrics = state.get("system_metrics", {})
    is_critical = metrics.get("error_rate_pct", 0) > 5.0 or metrics.get("severity") == "CRITICAL"
    state["is_critical"] = is_critical
    return is_critical

def trigger_auto_failover(state: Dict[str, Any]) -> str:
    """Step 3A: Trigger automatic Cloudflare failover endpoint."""
    state["remediation_action"] = "routed_traffic_to_standby_region"
    return "failover_triggered"

def log_minor_warning(state: Dict[str, Any]) -> str:
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

WORKFLOW_REGISTRY: Dict[str, Workflow] = {
    "customer_refund_workflow": customer_refund_workflow,
    "incident_response_workflow": incident_response_workflow,
}

def run_workflow_by_name(name: str, initial_state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Execute an ADK 2.0 graph workflow deterministically over state."""
    state = dict(initial_state or {})
    if name == "customer_refund_workflow":
        if "purchase_history" not in state:
            fetch_purchase_history(state)
        is_eligible = evaluate_eligibility_rule(state)
        if is_eligible:
            issue_refund(state)
        else:
            reject_refund(state)
        compose_notification(state)
        return state
    elif name == "incident_response_workflow":
        if "system_metrics" not in state:
            fetch_system_logs(state)
        is_critical = evaluate_severity_rule(state)
        if is_critical:
            trigger_auto_failover(state)
        else:
            log_minor_warning(state)
        return state
    else:
        raise ValueError(f"Unknown workflow: {name}")
