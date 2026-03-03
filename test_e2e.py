#!/usr/bin/env python3
"""
End-to-end test script for the Personal Assistant ADK.
Tests: imports, config validation, agent construction, and a live API call.

Usage:
    python test_e2e.py                    # Test imports + config only
    python test_e2e.py --live             # Also run a live LLM call
"""
import asyncio
import sys
import os
import time

from dotenv import load_dotenv
load_dotenv()

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
results = []

def test(name, fn):
    try:
        fn()
        results.append((name, True, None))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  {FAIL} {name}: {e}")


# ─── Test 1: Core ADK Imports ────────────────────────────────────────────────
print("\n[Test Suite] ADK Imports")

def t_agents_import():
    from google.adk.agents import Context, LlmAgent, SequentialAgent, ParallelAgent
test("agents package", t_agents_import)

def t_readonly_context():
    from google.adk.agents.readonly_context import ReadonlyContext
test("ReadonlyContext", t_readonly_context)

def t_callback_context():
    from google.adk.agents.callback_context import CallbackContext
test("CallbackContext", t_callback_context)

def t_models():
    from google.adk.models import LlmRequest, LlmResponse
test("models package", t_models)

def t_tools():
    from google.adk.tools import BaseTool, ToolContext, load_memory
    from google.adk.tools.preload_memory_tool import PreloadMemoryTool
test("tools package", t_tools)

def t_services():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.memory import InMemoryMemoryService
    from google.adk.artifacts import InMemoryArtifactService
test("services (runner, session, memory, artifacts)", t_services)


# ─── Test 2: Project Module Imports ──────────────────────────────────────────
print("\n[Test Suite] Project Modules")

def t_config():
    from personal_assistant.shared.config import validate_config, DEFAULT_MODEL, APP_NAME
    assert APP_NAME == "personal_assistant"
test("shared.config", t_config)

def t_callbacks():
    from personal_assistant.shared.callbacks import (
        before_agent_callback, after_agent_callback,
        before_model_callback, after_model_callback,
        before_tool_callback, after_tool_callback,
    )
test("shared.callbacks", t_callbacks)

def t_prompts():
    from personal_assistant.shared.prompts import root_instruction_provider
test("shared.prompts", t_prompts)

def t_root_agent():
    from personal_assistant.agent import root_agent
    assert root_agent.name == "personal_assistant"
    assert len(root_agent.sub_agents) == 9
test("root_agent (9 sub-agents)", t_root_agent)


# ─── Test 3: Config Validation ───────────────────────────────────────────────
print("\n[Test Suite] Configuration")

def t_validate():
    from personal_assistant.shared.config import validate_config
    cfg = validate_config()
    if cfg["errors"]:
        raise RuntimeError(f"Config errors: {cfg['errors']}")
test("validate_config (no errors)", t_validate)


# ─── Test 4: Live Agent Turn (optional) ──────────────────────────────────────
if "--live" in sys.argv:
    print("\n[Test Suite] Live Agent Turn")

    async def live_test():
        from personal_assistant.shared.config import (
            APP_NAME, create_session_service, create_memory_service,
            create_artifact_service,
        )
        from personal_assistant.agent import root_agent
        from google.adk.runners import Runner
        from google.genai import types as genai_types

        session_service = create_session_service()
        memory_service = create_memory_service()
        artifact_service = create_artifact_service()

        session = await session_service.create_session(
            app_name=APP_NAME, user_id="test", session_id="e2e_test",
            state={"user:name": "Jithendra"},
        )

        runner = Runner(
            agent=root_agent, app_name=APP_NAME,
            session_service=session_service,
            memory_service=memory_service,
            artifact_service=artifact_service,
        )

        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text="Hello! What can you help me with? Keep it brief.")],
        )

        response_text = ""
        start = time.time()
        async for event in runner.run_async(
            user_id="test", session_id="e2e_test", new_message=content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
        elapsed = time.time() - start

        if not response_text:
            raise RuntimeError("No response from agent")
        print(f"  Response ({elapsed:.1f}s): {response_text[:200]}...")
        return response_text

    def t_live():
        asyncio.run(live_test())

    test("live agent turn (LLM call)", t_live)


# ─── Summary ─────────────────────────────────────────────────────────────────
print(f"\n{'─' * 60}")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"Results: {passed} passed, {failed} failed, {len(results)} total")

if failed:
    print(f"\nFailed tests:")
    for name, ok, err in results:
        if not ok:
            print(f"  {FAIL} {name}: {err}")
    sys.exit(1)
else:
    print(f"\n{PASS} All tests passed!")
    sys.exit(0)
