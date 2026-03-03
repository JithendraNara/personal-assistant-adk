#!/usr/bin/env python3
"""
serve.py — FastAPI API server for the Personal Assistant.

Provides HTTP endpoints for interacting with the agent programmatically.
Suitable for deployment on Cloud Run, GKE, or any container platform.

Usage:
    uvicorn serve:app --host 0.0.0.0 --port 8080
    python serve.py  # Runs with uvicorn
"""

import os
import logging
from datetime import datetime, timezone
from uuid import uuid4
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from google.adk.runners import Runner
from google.genai import types as genai_types

from personal_assistant.shared.config import (
    APP_NAME, validate_config,
    create_session_service, create_memory_service, create_artifact_service,
)
from personal_assistant.agent import root_agent

logger = logging.getLogger(__name__)

# ─── Globals (initialized at startup) ────────────────────────────────────────
runner: Runner = None
session_service = None
memory_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global runner, session_service, memory_service

    cfg = validate_config()
    if cfg["errors"]:
        for err in cfg["errors"]:
            logger.error(f"Config error: {err}")
        raise RuntimeError("Configuration errors — cannot start server")

    session_service = create_session_service()
    memory_service = create_memory_service()
    artifact_service = create_artifact_service()

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
        artifact_service=artifact_service,
    )

    logger.info(f"Server started | Session: {type(session_service).__name__} | Memory: {type(memory_service).__name__}")
    yield
    logger.info("Server shutting down")


app = FastAPI(
    title="Personal Assistant API",
    description="Google ADK Multi-Agent Personal Assistant",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    user_id: str = Field(default="default", description="User identifier")
    session_id: str = Field(default=None, description="Session ID (auto-generated if not provided)")

class ChatResponse(BaseModel):
    response: str
    session_id: str
    agents_involved: list[str] = []
    turn_duration_ms: int = 0

class SessionCreateRequest(BaseModel):
    user_id: str = Field(default="default")
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


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        session_service=type(session_service).__name__,
        memory_service=type(memory_service).__name__,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message and get the agent's response."""
    import time
    start = time.time()

    user_id = request.user_id
    session_id = request.session_id

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
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if hasattr(event, 'author') and event.author and event.author not in agents_involved:
                agents_involved.append(event.author)
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_parts.append(part.text)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    duration_ms = int((time.time() - start) * 1000)

    return ChatResponse(
        response="".join(response_parts) or "[No response]",
        session_id=session_id,
        agents_involved=agents_involved,
        turn_duration_ms=duration_ms,
    )


@app.post("/sessions", response_model=SessionInfo)
async def create_session(request: SessionCreateRequest):
    """Create a new session."""
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
async def save_session_to_memory(user_id: str, session_id: str):
    """Manually save a session to long-term memory."""
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("serve:app", host="0.0.0.0", port=port, reload=True)
