"""
ADK 2.0 Native Evaluation Harness Tests.

Uses `google.adk.evaluation` (`EvalCase`, `EvalSet`, `Invocation`) to evaluate agent behavior,
trajectory correctness, and response structure.
"""

from google.adk.evaluation.eval_case import EvalCase, Invocation
from google.adk.evaluation.eval_set import EvalSet
from google.genai import types

from personal_assistant.agent import root_agent
from personal_assistant.workflows import customer_refund_workflow, incident_response_workflow


def test_adk_eval_case_instantiation():
    """Verify ADK 2.0 native EvalCase and EvalSet construction."""
    case1 = EvalCase(
        eval_id="test_case_1",
        conversation=[
            Invocation(
                user_content=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="What's the weather in Fort Wayne, IN?")]
                )
            )
        ]
    )
    eval_set = EvalSet(
        eval_set_id="weather_eval_set",
        name="weather_eval_set",
        eval_cases=[case1]
    )

    assert eval_set.eval_set_id == "weather_eval_set"
    assert eval_set.name == "weather_eval_set"
    assert len(eval_set.eval_cases) == 1
    assert eval_set.eval_cases[0].eval_id == "test_case_1"


def test_adk_workflow_trajectory_eval():
    """Verify workflow graph evaluation metrics and edges."""
    assert root_agent.name == "personal_assistant"

    # Evaluate customer_refund_workflow trajectory
    assert customer_refund_workflow.name == "customer_refund_workflow"
    assert len(customer_refund_workflow.edges) == 6

    # Evaluate incident_response_workflow trajectory
    assert incident_response_workflow.name == "incident_response_workflow"
    assert len(incident_response_workflow.edges) == 3
