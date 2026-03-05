#!/usr/bin/env python3
"""
End-to-end smoke test script for the Personal Assistant ADK.

This is a standalone script (not a pytest module).

Usage:
    python test_e2e.py         # imports + config only
    python test_e2e.py --live  # also run a live LLM call
"""

import asyncio
import sys
import time

from dotenv import load_dotenv

load_dotenv()

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"


def run_check(name, fn, results):
    try:
        fn()
        results.append((name, True, None))
        print(f"  {PASS} {name}")
    except Exception as exc:
        results.append((name, False, str(exc)))
        print(f"  {FAIL} {name}: {exc}")


def _run_live_check():
    async def live_test():
        from personal_assistant.shared.config import (
            APP_NAME,
            create_adk_app,
            create_artifact_service,
            create_memory_service,
            create_session_service,
        )
        from personal_assistant.agent import root_agent
        from google.adk.runners import Runner
        from google.genai import types as genai_types

        session_service = create_session_service()
        memory_service = create_memory_service()
        artifact_service = create_artifact_service()
        adk_runtime_app = create_adk_app(root_agent)

        await session_service.create_session(
            app_name=APP_NAME,
            user_id="test",
            session_id="e2e_test",
            state={"user:name": "Jithendra"},
        )

        runner = Runner(
            app=adk_runtime_app,
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
            user_id="test",
            session_id="e2e_test",
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
        elapsed = time.time() - start

        if not response_text:
            raise RuntimeError("No response from agent")
        print(f"  Response ({elapsed:.1f}s): {response_text[:200]}...")

    asyncio.run(live_test())


def run_suite(run_live: bool) -> int:
    results = []

    print("\n[Test Suite] ADK Imports")
    run_check("agents package", lambda: __import__("google.adk.agents"), results)
    run_check("ReadonlyContext", lambda: __import__("google.adk.agents.readonly_context"), results)
    run_check("CallbackContext", lambda: __import__("google.adk.agents.callback_context"), results)
    run_check("models package", lambda: __import__("google.adk.models"), results)
    run_check("tools package", lambda: __import__("google.adk.tools"), results)
    run_check("services (runner, session, memory, artifacts)", lambda: __import__("google.adk.runners"), results)

    print("\n[Test Suite] Project Modules")

    def t_config():
        from personal_assistant.shared.config import APP_NAME

        assert APP_NAME == "personal_assistant"

    run_check("shared.config", t_config, results)
    run_check("shared.callbacks", lambda: __import__("personal_assistant.shared.callbacks"), results)
    run_check("shared.prompts", lambda: __import__("personal_assistant.shared.prompts"), results)

    def t_root_agent():
        from personal_assistant.agent import root_agent

        assert root_agent.name == "personal_assistant"
        assert len(root_agent.sub_agents) == 9

    run_check("root_agent (9 sub-agents)", t_root_agent, results)

    print("\n[Test Suite] Configuration")

    def t_validate():
        from personal_assistant.shared.config import validate_config

        cfg = validate_config()
        if cfg["errors"]:
            raise RuntimeError(f"Config errors: {cfg['errors']}")

    run_check("validate_config (no errors)", t_validate, results)

    if run_live:
        print("\n[Test Suite] Live Agent Turn")
        run_check("live agent turn (LLM call)", _run_live_check, results)

    print(f"\n{'─' * 60}")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")

    if failed:
        print("\nFailed tests:")
        for name, ok, err in results:
            if not ok:
                print(f"  {FAIL} {name}: {err}")
        return 1

    print(f"\n{PASS} All tests passed!")
    return 0


def main(argv: list[str]) -> int:
    return run_suite(run_live="--live" in argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
