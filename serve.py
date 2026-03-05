#!/usr/bin/env python3
"""
serve.py — FastAPI API server for the Personal Assistant.

Provides HTTP endpoints for interacting with the agent programmatically.
Suitable for deployment on Cloud Run, GKE, or any container platform.

Usage:
    uvicorn serve:app --host 0.0.0.0 --port 8080
    python serve.py  # Runs with uvicorn
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional, Any, Literal
from datetime import datetime, timezone
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from google.adk.runners import Runner
from google.adk.agents.run_config import StreamingMode
from google.adk.runners import RunConfig
from google.genai import types as genai_types

from personal_assistant.shared.config import (
    APP_NAME,
    MAX_INPUT_CHARS,
    get_cors_origins,
    validate_config,
    create_session_service,
    create_memory_service,
    create_artifact_service,
    create_adk_app,
    create_default_run_config,
)
from personal_assistant.agent import root_agent
from personal_assistant.shared.security import (
    check_api_key,
    check_rate_limit,
    resolve_api_key,
)

logger = logging.getLogger(__name__)

# ─── Globals (initialized at startup) ────────────────────────────────────────
runner: Optional[Runner] = None
session_service = None
memory_service = None
adk_runtime_app = None
default_run_config: RunConfig | None = None
DASHBOARD_DIR = Path(__file__).resolve().parent / "personal_assistant" / "dashboard"
MISSION_CONTROL_PAGES = {
    "overview": "mission_control_overview.html",
    "sessions": "mission_control_sessions.html",
    "agents": "mission_control_agents.html",
    "console": "mission_control_console.html",
}


class MissionControlTelemetry:
    """In-process telemetry store for mission control dashboards."""

    def __init__(self):
        self.started_at = time.time()
        self.total_turns = 0
        self.total_errors = 0
        self.total_latency_ms = 0
        self.sessions: dict[str, dict[str, Any]] = {}
        self.events: deque[dict[str, Any]] = deque(maxlen=800)
        self.agent_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "turns": 0,
                "errors": 0,
                "tool_calls": 0,
                "total_latency_ms": 0,
                "last_seen_at": None,
            }
        )
        self._session_tool_offsets: dict[str, int] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _status(last_event_ts: float) -> str:
        if time.time() - last_event_ts <= 180:
            return "active"
        if time.time() - last_event_ts <= 1800:
            return "idle"
        return "cold"

    async def consume_tool_calls(
        self, session_id: str, tool_calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not session_id:
            return []

        async with self._lock:
            offset = self._session_tool_offsets.get(session_id, 0)
            if offset < 0 or offset > len(tool_calls):
                offset = len(tool_calls)
            delta = tool_calls[offset:]
            self._session_tool_offsets[session_id] = len(tool_calls)
            return [item for item in delta if isinstance(item, dict)]

    async def record_turn(
        self,
        *,
        session_id: str,
        user_id: str,
        source: str,
        message: str,
        response: str,
        agents: list[str],
        duration_ms: int,
        error: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        now_ts = time.time()
        now_iso = self._now_iso()
        safe_message = (message or "").strip()
        safe_response = (response or "").strip()
        route = [agent for agent in agents if isinstance(agent, str) and agent]
        route_chain = " -> ".join(route) if route else "unresolved"
        tool_calls = tool_calls or []

        async with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                session = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "source": source,
                    "created_at": now_iso,
                    "turns": 0,
                    "errors": 0,
                    "tool_calls": 0,
                    "last_message": "",
                    "last_response": "",
                    "last_agents": [],
                    "last_route": "unresolved",
                    "last_duration_ms": 0,
                    "last_event_ts": now_ts,
                    "last_event_at": now_iso,
                }
                self.sessions[session_id] = session

            session["user_id"] = user_id
            session["source"] = source
            session["turns"] += 1
            session["last_event_ts"] = now_ts
            session["last_event_at"] = now_iso
            session["last_message"] = safe_message[:220]
            session["last_response"] = safe_response[:300]
            session["last_agents"] = route
            session["last_route"] = route_chain
            session["last_duration_ms"] = max(duration_ms, 0)

            if error:
                session["errors"] += 1
                self.total_errors += 1

            self.total_turns += 1
            self.total_latency_ms += max(duration_ms, 0)

            for agent_name in route:
                stats = self.agent_stats[agent_name]
                stats["turns"] += 1
                stats["total_latency_ms"] += max(duration_ms, 0)
                stats["last_seen_at"] = now_iso
                if error:
                    stats["errors"] += 1

            for tool_call in tool_calls:
                tool_name = str(tool_call.get("tool", "unknown_tool"))
                tool_agent = str(tool_call.get("agent", "unknown_agent"))
                session["tool_calls"] += 1
                tool_stats = self.agent_stats[tool_agent]
                tool_stats["tool_calls"] += 1
                tool_stats["last_seen_at"] = now_iso
                self.events.appendleft(
                    {
                        "event": "tool",
                        "timestamp": now_iso,
                        "session_id": session_id,
                        "user_id": user_id,
                        "source": source,
                        "agent": tool_agent,
                        "message": f"{tool_agent} -> {tool_name}",
                    }
                )

            self.events.appendleft(
                {
                    "event": "error" if error else "turn",
                    "timestamp": now_iso,
                    "session_id": session_id,
                    "user_id": user_id,
                    "source": source,
                    "agent": route[-1] if route else "unknown",
                    "route": route_chain,
                    "duration_ms": max(duration_ms, 0),
                    "message": (error or safe_message[:180] or "[empty message]"),
                }
            )

    async def snapshot(self, *, max_sessions: int, max_events: int) -> dict[str, Any]:
        async with self._lock:
            sorted_sessions = sorted(
                self.sessions.values(),
                key=lambda item: item.get("last_event_ts", 0),
                reverse=True,
            )[:max_sessions]
            sessions = [
                {
                    **session,
                    "status": self._status(session.get("last_event_ts", 0)),
                }
                for session in sorted_sessions
            ]

            agents = []
            for name, stats in self.agent_stats.items():
                turns = stats["turns"]
                avg_latency = int(stats["total_latency_ms"] / turns) if turns else 0
                agents.append(
                    {
                        "name": name,
                        "turns": turns,
                        "errors": stats["errors"],
                        "tool_calls": stats["tool_calls"],
                        "avg_latency_ms": avg_latency,
                        "last_seen_at": stats["last_seen_at"],
                    }
                )
            agents.sort(key=lambda item: item["turns"], reverse=True)

            total_turns = self.total_turns
            avg_latency = int(self.total_latency_ms / total_turns) if total_turns else 0
            active_sessions = sum(
                1
                for session in self.sessions.values()
                if self._status(session.get("last_event_ts", 0)) == "active"
            )

            return {
                "generated_at": self._now_iso(),
                "uptime_seconds": int(max(time.time() - self.started_at, 0)),
                "overview": {
                    "total_turns": total_turns,
                    "active_sessions": active_sessions,
                    "tracked_sessions": len(self.sessions),
                    "avg_latency_ms": avg_latency,
                    "error_rate": round((self.total_errors / total_turns) * 100, 2)
                    if total_turns
                    else 0.0,
                    "total_errors": self.total_errors,
                },
                "agents": agents,
                "sessions": sessions,
                "events": list(self.events)[:max_events],
            }


mission_control = MissionControlTelemetry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global runner, session_service, memory_service, adk_runtime_app, default_run_config

    cfg = validate_config()
    if cfg["errors"]:
        for err in cfg["errors"]:
            logger.error(f"Config error: {err}")
        raise RuntimeError("Configuration errors — cannot start server")

    session_service = create_session_service()
    memory_service = create_memory_service()
    artifact_service = create_artifact_service()
    adk_runtime_app = create_adk_app(root_agent)
    default_run_config = create_default_run_config()

    runner = Runner(
        app=adk_runtime_app,
        session_service=session_service,
        memory_service=memory_service,
        artifact_service=artifact_service,
    )

    logger.info(
        f"Server started | Session: {type(session_service).__name__} | Memory: {type(memory_service).__name__}"
    )

    # Register A2A protocol routes (agent discovery + task endpoint)
    try:
        from personal_assistant.shared.a2a import register_a2a_routes
        register_a2a_routes(
            app,
            runner,
            session_service,
            APP_NAME,
            auth_validator=check_api_key,
        )
        logger.info("A2A routes registered (/.well-known/agent.json, /a2a)")
    except Exception as e:
        logger.warning(f"A2A routes not registered: {e}")

    yield
    logger.info("Server shutting down")


app = FastAPI(
    title="Personal Assistant API",
    description="Google ADK Multi-Agent Personal Assistant",
    version="2.0.0",
    lifespan=lifespan,
)

if DASHBOARD_DIR.exists():
    app.mount(
        "/mission-control/assets",
        StaticFiles(directory=DASHBOARD_DIR),
        name="mission_control_assets",
    )

# CORS — environment-aware (OpenClaw security pattern)
_cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ─────────────────────────────────────────────────

class RunConfigOverrides(BaseModel):
    save_input_blobs_as_artifacts: bool | None = None
    max_llm_calls: int | None = Field(default=None, ge=1, le=5000)
    streaming_mode: Literal["none", "sse", "bidi"] | None = None
    session_resumption_handle: str | None = None
    session_resumption_transparent: bool | None = None


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_INPUT_CHARS,
        description="User message",
    )
    user_id: str = Field(default="default", min_length=1, max_length=128, description="User identifier")
    session_id: str = Field(default=None, description="Session ID (auto-generated if not provided)")
    invocation_id: str | None = Field(default=None, description="Optional invocation ID for resumable runs")
    state_delta: dict[str, Any] | None = Field(
        default=None,
        description="Optional state delta merged before execution",
    )
    run_config: RunConfigOverrides | None = Field(
        default=None,
        description="Optional per-request ADK RunConfig overrides",
    )

class ChatResponse(BaseModel):
    response: str
    session_id: str
    agents_involved: list[str] = []
    turn_duration_ms: int = 0

class SessionCreateRequest(BaseModel):
    user_id: str = Field(default="default", min_length=1, max_length=128)
    initial_state: dict = Field(default_factory=dict)

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    created_at: str

class HealthResponse(BaseModel):
    status: str
    version: str
    session_service: str
    memory_service: str


def _build_run_config(overrides: RunConfigOverrides | None = None) -> RunConfig | None:
    kwargs: dict[str, Any] = {}
    if default_run_config is not None:
        kwargs.update(default_run_config.model_dump(exclude_none=True))

    if overrides:
        if overrides.save_input_blobs_as_artifacts is not None:
            kwargs["save_input_blobs_as_artifacts"] = overrides.save_input_blobs_as_artifacts
        if overrides.max_llm_calls is not None:
            kwargs["max_llm_calls"] = overrides.max_llm_calls
        if overrides.streaming_mode is not None:
            kwargs["streaming_mode"] = {
                "none": StreamingMode.NONE,
                "sse": StreamingMode.SSE,
                "bidi": StreamingMode.BIDI,
            }[overrides.streaming_mode]
        if (
            overrides.session_resumption_handle is not None
            or overrides.session_resumption_transparent is not None
        ):
            kwargs["session_resumption"] = genai_types.SessionResumptionConfig(
                handle=overrides.session_resumption_handle,
                transparent=overrides.session_resumption_transparent,
            )

    if not kwargs:
        return None
    return RunConfig(**kwargs)


def _request_client_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


async def require_api_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str:
    """
    Validate API access token from headers.

    Returns a stable caller identity key for rate limiting.
    """
    api_key = resolve_api_key(
        x_api_key=x_api_key,
        authorization_header=authorization,
    )
    allowed, reason = check_api_key(api_key)
    if not allowed:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {reason}")
    return api_key or _request_client_key(request)


def enforce_rate_limit(rate_key: str) -> None:
    """Apply global per-minute rate limit."""
    allowed, retry_after = check_rate_limit(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


async def _consume_recent_tool_calls(user_id: str, session_id: str) -> list[dict[str, Any]]:
    """
    Read tool call entries from session state and return only unseen rows.

    This allows the mission control panel to display tool activity without changing
    ADK callback behavior.
    """
    if not session_id or session_service is None:
        return []

    try:
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        return []

    if not session:
        return []

    state = getattr(session, "state", None)
    if not isinstance(state, dict):
        return []

    tool_calls = state.get("_tool_calls", [])
    if not isinstance(tool_calls, list):
        return []

    return await mission_control.consume_tool_calls(session_id, tool_calls)


async def _record_mission_control_turn(
    *,
    session_id: str | None,
    user_id: str,
    source: str,
    message: str,
    response: str,
    agents: list[str],
    duration_ms: int,
    error: str | None = None,
) -> None:
    """Best-effort telemetry recording that never blocks request completion."""
    if not session_id:
        return

    try:
        tool_calls = await _consume_recent_tool_calls(user_id, session_id)
        await mission_control.record_turn(
            session_id=session_id,
            user_id=user_id,
            source=source,
            message=message,
            response=response,
            agents=agents,
            duration_ms=duration_ms,
            error=error,
            tool_calls=tool_calls,
        )
    except Exception as telemetry_error:
        logger.warning("Mission control telemetry recording failed: %s", telemetry_error)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        session_service=type(session_service).__name__,
        memory_service=type(memory_service).__name__,
    )


def _read_mission_control_page(page_key: str) -> str:
    filename = MISSION_CONTROL_PAGES.get(page_key)
    if not filename:
        raise HTTPException(status_code=404, detail="Mission control page not found.")
    page_path = DASHBOARD_DIR / filename
    if not page_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Mission control page asset missing: {filename}",
        )
    return page_path.read_text(encoding="utf-8")


@app.get("/mission-control", response_class=HTMLResponse)
@app.get("/mission-control/overview", response_class=HTMLResponse)
async def mission_control_dashboard():
    """Mission control overview page."""
    return HTMLResponse(content=_read_mission_control_page("overview"))


@app.get("/mission-control/sessions", response_class=HTMLResponse)
async def mission_control_sessions_page():
    """Mission control sessions page."""
    return HTMLResponse(content=_read_mission_control_page("sessions"))


@app.get("/mission-control/agents", response_class=HTMLResponse)
async def mission_control_agents_page():
    """Mission control agents page."""
    return HTMLResponse(content=_read_mission_control_page("agents"))


@app.get("/mission-control/console", response_class=HTMLResponse)
async def mission_control_console_page():
    """Mission control operator console page."""
    return HTMLResponse(content=_read_mission_control_page("console"))


@app.get("/api/mission-control/snapshot")
async def mission_control_snapshot(
    raw_request: Request,
    max_sessions: int = Query(default=40, ge=1, le=200),
    max_events: int = Query(default=200, ge=10, le=800),
    auth_key: str = Depends(require_api_access),
):
    """Return aggregated mission-control telemetry + runtime status."""
    enforce_rate_limit(
        f"http:mission_control_snapshot:{auth_key}:{_request_client_key(raw_request)}"
    )

    snapshot = await mission_control.snapshot(
        max_sessions=max_sessions,
        max_events=max_events,
    )
    snapshot["runtime"] = {
        "app_name": APP_NAME,
        "model": str(getattr(root_agent, "model", "unknown")),
        "session_service": type(session_service).__name__ if session_service else None,
        "memory_service": type(memory_service).__name__ if memory_service else None,
        "plugins_loaded": len(getattr(adk_runtime_app, "plugins", []) or []),
        "agents": [a.name for a in root_agent.sub_agents] if hasattr(root_agent, "sub_agents") else [],
    }
    return snapshot


@app.get("/api/mission-control/sessions/{session_id}")
async def mission_control_session_detail(
    session_id: str,
    raw_request: Request,
    auth_key: str = Depends(require_api_access),
):
    """Inspect details for a specific session, including ADK state keys."""
    enforce_rate_limit(
        f"http:mission_control_session_detail:{auth_key}:{_request_client_key(raw_request)}"
    )

    snapshot = await mission_control.snapshot(max_sessions=400, max_events=800)
    session_entry = next(
        (session for session in snapshot["sessions"] if session["session_id"] == session_id),
        None,
    )
    if session_entry is None:
        raise HTTPException(status_code=404, detail="Session not tracked yet.")

    adk_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=session_entry["user_id"],
        session_id=session_id,
    )
    state = getattr(adk_session, "state", {}) if adk_session else {}
    state_keys = sorted(state.keys()) if isinstance(state, dict) else []
    tool_calls = state.get("_tool_calls", []) if isinstance(state, dict) else []

    return {
        "session": session_entry,
        "state_keys": state_keys,
        "state_key_count": len(state_keys),
        "recent_tool_calls": tool_calls[-20:] if isinstance(tool_calls, list) else [],
        "events": [
            event
            for event in snapshot["events"]
            if event.get("session_id") == session_id
        ][:200],
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    raw_request: Request,
    auth_key: str = Depends(require_api_access),
):
    """Send a message and get the agent's response."""
    start = time.time()

    user_id = request.user_id
    session_id = request.session_id
    enforce_rate_limit(f"http:chat:{auth_key}:{_request_client_key(raw_request)}")

    # Auto-create session if needed
    if not session_id:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        session_id = f"session_{today}_{uuid4().hex[:6]}"
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"user:name": user_id},
        )

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=request.message)],
    )

    response_parts = []
    agents_involved = []

    try:
        effective_run_config = _build_run_config(request.run_config)
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            invocation_id=request.invocation_id,
            state_delta=request.state_delta,
            new_message=content,
            run_config=effective_run_config,
        ):
            if hasattr(event, "author") and event.author and event.author not in agents_involved:
                agents_involved.append(event.author)
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_parts.append(part.text)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        duration_ms = int((time.time() - start) * 1000)
        await _record_mission_control_turn(
            session_id=session_id,
            user_id=user_id,
            source="http",
            message=request.message,
            response="",
            agents=agents_involved,
            duration_ms=duration_ms,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))

    duration_ms = int((time.time() - start) * 1000)
    response_text = "".join(response_parts) or "[No response]"

    await _record_mission_control_turn(
        session_id=session_id,
        user_id=user_id,
        source="http",
        message=request.message,
        response=response_text,
        agents=agents_involved,
        duration_ms=duration_ms,
    )

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        agents_involved=agents_involved,
        turn_duration_ms=duration_ms,
    )


@app.post("/sessions", response_model=SessionInfo)
async def create_session(
    request: SessionCreateRequest,
    raw_request: Request,
    auth_key: str = Depends(require_api_access),
):
    """Create a new session."""
    enforce_rate_limit(f"http:sessions:{auth_key}:{_request_client_key(raw_request)}")

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    session_id = f"session_{today}_{uuid4().hex[:6]}"

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=request.user_id,
        session_id=session_id,
        state=request.initial_state,
    )

    return SessionInfo(
        session_id=session_id,
        user_id=request.user_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/memory/save")
async def save_session_to_memory(
    raw_request: Request,
    user_id: str = Query(..., min_length=1, max_length=128),
    session_id: str = Query(..., min_length=1, max_length=256),
    auth_key: str = Depends(require_api_access),
):
    """Manually save a session to long-term memory."""
    enforce_rate_limit(f"http:memory_save:{auth_key}:{_request_client_key(raw_request)}")

    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if session:
            await memory_service.add_session_to_memory(session)
            return {"status": "saved"}
        raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config")
async def get_config(
    raw_request: Request,
    auth_key: str = Depends(require_api_access),
):
    """Runtime config introspection (OpenClaw gateway config concept)."""
    enforce_rate_limit(f"http:config:{auth_key}:{_request_client_key(raw_request)}")

    return {
        "app_name": APP_NAME,
        "session_service": type(session_service).__name__ if session_service else None,
        "memory_service": type(memory_service).__name__ if memory_service else None,
        "cors_origins": _cors_origins,
        "agents": [a.name for a in root_agent.sub_agents] if hasattr(root_agent, "sub_agents") else [],
    }


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time agent streaming (OpenClaw gateway pattern)."""
    api_key = resolve_api_key(
        x_api_key=websocket.headers.get("x-api-key"),
        authorization_header=websocket.headers.get("authorization"),
        query_api_key=websocket.query_params.get("api_key"),
    )
    allowed, reason = check_api_key(api_key)
    if not allowed:
        await websocket.close(code=4401, reason=f"Unauthorized: {reason}")
        return

    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "error": "Invalid JSON payload"}))
                continue

            message = payload.get("message", "")
            user_id = payload.get("user_id", "default")
            session_id = payload.get("session_id")
            invocation_id = payload.get("invocation_id")
            state_delta = payload.get("state_delta")
            if state_delta is not None and not isinstance(state_delta, dict):
                await websocket.send_text(json.dumps({"type": "error", "error": "state_delta must be an object"}))
                continue

            run_config_payload = payload.get("run_config")
            overrides: RunConfigOverrides | None = None
            if run_config_payload is not None:
                try:
                    overrides = RunConfigOverrides.model_validate(run_config_payload)
                except ValidationError as ve:
                    await websocket.send_text(
                        json.dumps({"type": "error", "error": f"Invalid run_config: {ve.errors()}"})
                    )
                    continue
            effective_run_config = _build_run_config(overrides)

            if not isinstance(message, str) or not message.strip():
                await websocket.send_text(json.dumps({"type": "error", "error": "Message must be non-empty text"}))
                continue
            if len(message) > MAX_INPUT_CHARS:
                await websocket.send_text(
                    json.dumps({"type": "error", "error": f"Message exceeds {MAX_INPUT_CHARS} characters"})
                )
                continue

            ws_client = websocket.client.host if websocket.client else "unknown"
            rate_key = f"ws:chat:{api_key or ws_client}:{ws_client}:{user_id}"
            allowed_rate, retry_after = check_rate_limit(rate_key)
            if not allowed_rate:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "error": "Rate limit exceeded",
                            "retry_after": retry_after,
                        }
                    )
                )
                continue

            if not session_id:
                today = datetime.now(timezone.utc).strftime("%Y%m%d")
                session_id = f"session_{today}_{uuid4().hex[:6]}"
                await session_service.create_session(
                    app_name=APP_NAME,
                    user_id=user_id,
                    session_id=session_id,
                    state={"user:name": user_id},
                )

            content = genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=message)],
            )
            start = time.time()
            response_parts: list[str] = []
            agents_involved: list[str] = []

            try:
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    invocation_id=invocation_id,
                    state_delta=state_delta,
                    new_message=content,
                    run_config=effective_run_config,
                ):
                    author = getattr(event, "author", None)
                    if author and author not in agents_involved:
                        agents_involved.append(author)

                    event_data = {
                        "type": "event",
                        "author": author,
                        "is_final": event.is_final_response(),
                        "session_id": session_id,
                    }
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                event_data["text"] = part.text
                                await websocket.send_text(json.dumps(event_data))
                                if event.is_final_response():
                                    response_parts.append(part.text)
            except Exception as ws_turn_error:
                duration_ms = int((time.time() - start) * 1000)
                await _record_mission_control_turn(
                    session_id=session_id,
                    user_id=user_id,
                    source="ws",
                    message=message,
                    response="",
                    agents=agents_involved,
                    duration_ms=duration_ms,
                    error=str(ws_turn_error),
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "error": str(ws_turn_error),
                            "session_id": session_id,
                        }
                    )
                )
                continue

            duration_ms = int((time.time() - start) * 1000)
            response_text = "".join(response_parts) or "[No response]"
            await _record_mission_control_turn(
                session_id=session_id,
                user_id=user_id,
                source="ws",
                message=message,
                response=response_text,
                agents=agents_involved,
                duration_ms=duration_ms,
            )
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "done",
                        "session_id": session_id,
                        "turn_duration_ms": duration_ms,
                    }
                )
            )
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.close(code=1011, reason=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "127.0.0.1")
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    uvicorn.run("serve:app", host=host, port=port, reload=env != "production")
