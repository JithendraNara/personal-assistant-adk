"""
A2A (Agent-to-Agent) Protocol support — Agent Card and A2A endpoint.

Exposes the Personal Assistant as a discoverable A2A agent with:
  - Agent Card at /.well-known/agent.json
  - Skill definitions for agent routing
  - A2A-compatible HTTP endpoint

References:
  - https://a2aprotocol.ai
  - https://google.github.io/adk-docs/a2a/
"""

import os
import logging
from typing import Callable

logger = logging.getLogger(__name__)


# ─── Agent Card Definition ────────────────────────────────────────────────────

def build_agent_card(
    base_url: str = "http://localhost:8080",
    version: str = "2.0.0",
) -> dict:
    """
    Build an A2A-compliant Agent Card for the Personal Assistant.

    The Agent Card is a JSON document served at /.well-known/agent.json
    that describes the agent's capabilities, skills, and how to interact with it.

    Args:
        base_url: The base URL where this agent is hosted.
        version: Agent version string.

    Returns:
        A2A AgentCard as a dict.
    """
    from personal_assistant.shared.security import is_auth_required

    auth_block: dict
    if is_auth_required():
        auth_block = {
            "schemes": ["apiKey"],
            "apiKey": {"name": "X-API-Key", "in": "header"},
        }
    else:
        auth_block = {"schemes": ["none"]}

    return {
        "name": "Personal Assistant",
        "description": (
            "A multi-agent personal assistant powered by Google ADK and Gemini. "
            "Handles research, scheduling, finance, career, sports, data analysis, "
            "and technology queries through specialized sub-agents."
        ),
        "url": f"{base_url}/a2a",
        "version": version,
        "protocol": "a2a",
        "protocolVersion": "0.3",
        "provider": {
            "organization": "Personal Assistant ADK",
            "url": base_url,
        },
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "authentication": auth_block,
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": _build_skill_definitions(),
    }


def _build_skill_definitions() -> list[dict]:
    """Define A2A skill entries for each specialist agent."""
    return [
        {
            "id": "research",
            "name": "Web Research",
            "description": "Search the web, fetch pages, summarize content, get news headlines.",
            "tags": ["search", "research", "news", "summarization"],
            "examples": [
                "Research the latest trends in AI agents",
                "Get today's tech news",
                "Summarize this webpage",
            ],
        },
        {
            "id": "scheduling",
            "name": "Task Management & Scheduling",
            "description": "Create tasks, set reminders, build daily plans, manage task status.",
            "tags": ["tasks", "schedule", "planning", "reminders"],
            "examples": [
                "Create a task to review PRs with high priority",
                "Build my daily plan for today",
                "Set a reminder for the standup at 10am",
            ],
        },
        {
            "id": "finance",
            "name": "Financial Analysis",
            "description": "Stock quotes, budget analysis, compound interest calculations, portfolio review.",
            "tags": ["finance", "stocks", "budgeting", "investing"],
            "examples": [
                "Get the stock quote for GOOGL",
                "Analyze my monthly budget",
                "Calculate compound interest on $10,000",
            ],
        },
        {
            "id": "career",
            "name": "Career Development",
            "description": "Job search, skill gap analysis, resume suggestions, offer comparison.",
            "tags": ["career", "jobs", "resume", "skills"],
            "examples": [
                "Search for senior Python developer jobs in NYC",
                "Analyze my skill gaps for a data engineering role",
            ],
        },
        {
            "id": "sports",
            "name": "Sports Updates",
            "description": "NFL scores, F1 standings, cricket scores and live updates.",
            "tags": ["sports", "nfl", "f1", "cricket"],
            "examples": [
                "Get today's NFL scores",
                "What are the F1 standings?",
                "Latest cricket scores",
            ],
        },
        {
            "id": "data_analysis",
            "name": "Data Analysis",
            "description": "CSV profiling, SQL generation, data visualization, anomaly detection.",
            "tags": ["data", "csv", "sql", "analytics", "visualization"],
            "examples": [
                "Profile this CSV file",
                "Generate a SQL query for user retention",
            ],
        },
        {
            "id": "technology",
            "name": "Technology Advisory",
            "description": "Code review, technology comparisons, architecture evaluation, tech summaries.",
            "tags": ["code", "architecture", "technology", "review"],
            "examples": [
                "Compare React vs Vue for a new project",
                "Review this Python function",
                "Evaluate this microservices architecture",
            ],
        },
    ]


# ─── FastAPI Integration ─────────────────────────────────────────────────────

def register_a2a_routes(
    app,
    runner,
    session_service,
    APP_NAME: str,
    auth_validator: Callable[[str | None], tuple[bool, str]] | None = None,
):
    """
    Register A2A protocol routes on an existing FastAPI app.

    Call from serve.py to add A2A support alongside the existing API.

    Args:
        app: The FastAPI app instance.
        runner: The ADK Runner instance.
        session_service: The session service.
        APP_NAME: Application name for session scoping.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from uuid import uuid4
    from google.genai import types as genai_types
    from personal_assistant.shared.security import resolve_api_key

    base_url = os.getenv("A2A_BASE_URL", "http://localhost:8080")
    agent_card = build_agent_card(base_url=base_url)

    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """A2A Agent Card endpoint — agent discovery."""
        return JSONResponse(content=agent_card)

    @app.post("/a2a")
    async def a2a_endpoint(request: Request, request_body: dict):
        """
        A2A protocol endpoint — receives tasks from other agents.

        Simplified implementation handling the core A2A task lifecycle:
          1. Receive task with input text
          2. Route through ADK agent
          3. Return result
        """
        if auth_validator:
            api_key = resolve_api_key(
                x_api_key=request.headers.get("x-api-key"),
                authorization_header=request.headers.get("authorization"),
                query_api_key=request.query_params.get("api_key"),
            )
            allowed, reason = auth_validator(api_key)
            if not allowed:
                return JSONResponse(
                    status_code=401,
                    content={
                        "jsonrpc": "2.0",
                        "id": request_body.get("id"),
                        "error": {"code": -32600, "message": f"Unauthorized: {reason}"},
                    },
                )

        task_id = request_body.get("params", {}).get("id", str(uuid4()))
        message_text = ""

        # Extract input text from A2A message format
        params = request_body.get("params", {})
        if "message" in params:
            parts = params["message"].get("parts", [])
            for part in parts:
                if part.get("type") == "text":
                    message_text = part.get("text", "")
                    break

        if not message_text:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": request_body.get("id"),
                "error": {"code": -32602, "message": "No input text found in message"},
            })

        # Create a session for this A2A task
        user_id = f"a2a_{task_id[:8]}"
        session_id = f"a2a_session_{uuid4().hex[:8]}"
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"source": "a2a", "task_id": task_id},
        )

        # Run the agent
        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message_text)],
        )

        response_parts = []
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_parts.append(part.text)

        response_text = "".join(response_parts) or "[No response]"

        # Return A2A-compliant response
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": request_body.get("id"),
            "result": {
                "id": task_id,
                "status": {"state": "completed"},
                "artifacts": [{
                    "parts": [{"type": "text", "text": response_text}],
                }],
            },
        })
