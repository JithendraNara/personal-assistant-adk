#!/usr/bin/env python3
"""
run.py — Interactive CLI runner for the Personal Assistant.

Usage:
    python run.py                           # Start new session
    python run.py --session-id my-session   # Resume session
    python run.py --user-id jithendra       # Set user ID
    python run.py --persistent              # Use SQLite persistence

Alternative:
    adk web personal_assistant              # Dev UI
    adk run personal_assistant              # Simple CLI
"""

import asyncio
import argparse
import sys
import os
import logging
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

from personal_assistant.shared.config import (
    validate_config, APP_NAME, USER_PROFILE,
    create_session_service, create_memory_service, create_artifact_service,
)
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from personal_assistant.agent import root_agent

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("runner")

# ─── ANSI Colors ──────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
MAGENTA = "\033[95m"


def print_banner():
    print(f"""
{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════════════╗
║           Personal Assistant — Google ADK v2                     ║
║           Multi-Agent • OpenClaw-inspired Architecture           ║
║           Powered by Gemini 2.0 Flash                            ║
╚══════════════════════════════════════════════════════════════════╝
{RESET}""")


def print_agent_list():
    agents = [
        ("research_agent", "Web search, news, summarization"),
        ("data_agent", "CSV analysis, SQL generation, data profiling"),
        ("career_agent", "Job search, skill gaps, salary benchmarks"),
        ("finance_agent", "Budgeting, stocks, portfolio analysis"),
        ("sports_agent", "NFL, Cricket, F1 scores & standings"),
        ("scheduler_agent", "Tasks, daily planning, reminders"),
        ("tech_agent", "Code review, tech comparisons, streaming setup"),
        ("daily_briefing", "Sequential: weather → tasks → news → summary"),
        ("info_gatherer", "Parallel: weather + sports + finance concurrent"),
    ]
    print(f"{DIM}Available agents:{RESET}")
    for name, desc in agents:
        icon = "⚡" if name in ("daily_briefing", "info_gatherer") else "•"
        print(f"  {CYAN}{icon}{RESET} {BOLD}{name}{RESET} — {desc}")
    print()


async def run_turn(runner: Runner, session_id: str, user_id: str, message: str) -> str:
    """Send one message and collect the full response."""
    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    response_parts = []
    agents_involved = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        # Track which agents are involved
        if hasattr(event, 'author') and event.author and event.author not in agents_involved:
            agents_involved.append(event.author)

        # Collect final response text
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_parts.append(part.text)

    # Show agent routing info
    if len(agents_involved) > 1:
        route = " → ".join(agents_involved)
        print(f"{DIM}  [Route: {route}]{RESET}")

    return "".join(response_parts) or "[No response received]"


async def save_to_memory(memory_service, session_service, session_id: str, user_id: str):
    """Save current session to long-term memory."""
    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if session:
            await memory_service.add_session_to_memory(session)
            logger.info("Session saved to memory")
    except Exception as e:
        logger.warning(f"Could not save to memory: {e}")


async def main(session_id: str = None, user_id: str = None, persistent: bool = False) -> None:
    """Main interactive CLI loop."""

    # Validate config
    cfg = validate_config()
    if cfg["errors"]:
        print(f"\n{RED}{BOLD}Configuration errors:{RESET}")
        for err in cfg["errors"]:
            print(f"  {RED}✗{RESET} {err}")
        print(f"\nCreate a {BOLD}.env{RESET} file from {BOLD}.env.example{RESET}.\n")
        sys.exit(1)

    if cfg["warnings"]:
        print(f"\n{YELLOW}{BOLD}Warnings:{RESET}")
        for warn in cfg["warnings"]:
            print(f"  {YELLOW}⚠{RESET} {warn}")
        print()

    # Set up services
    if persistent:
        os.environ["ENVIRONMENT"] = "production"
    session_service = create_session_service()
    memory_service = create_memory_service()
    artifact_service = create_artifact_service()

    service_type = type(session_service).__name__
    logger.info(f"Session service: {service_type}")
    logger.info(f"Memory service: {type(memory_service).__name__}")

    user_id = user_id or USER_PROFILE["name"].lower()

    # Date-scoped session ID (daily rotation like OpenClaw)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    session_id = session_id or f"session_{today}_{uuid4().hex[:6]}"

    # Create session with pre-populated state
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={
            "user:name": USER_PROFILE["name"],
            "user:locations": USER_PROFILE["locations"],
            "user:interests": USER_PROFILE["interests"],
            "user:nfl_team": USER_PROFILE["nfl_team"],
            "user:f1_follows": USER_PROFILE["f1_follows"],
            "scheduler_tasks": [],
            "scheduler_reminders": [],
        },
    )

    # Set up runner with all services
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
        artifact_service=artifact_service,
    )

    # UI
    print_banner()
    print(f"{DIM}User: {USER_PROFILE['name']} | {USER_PROFILE['locations']['primary']} | {service_type}{RESET}")
    print(f"{DIM}Session: {session_id}{RESET}\n")
    print_agent_list()
    print(f"{DIM}Commands: help, agents, session, save, clear, quit{RESET}\n")
    print(f"{BOLD}{'─' * 64}{RESET}\n")

    # Interactive loop
    turn_count = 0
    try:
        while True:
            try:
                user_input = input(f"\n{GREEN}{BOLD}You:{RESET} ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ("quit", "exit", "q"):
                await save_to_memory(memory_service, session_service, session_id, user_id)
                print(f"\n{DIM}Session saved. Goodbye!{RESET}\n")
                break
            elif cmd == "help":
                print(f"""
{BOLD}Commands:{RESET}
  help       — Show this message
  agents     — List specialist agents
  session    — Show session info
  save       — Save session to memory
  clear      — Clear screen
  briefing   — Run daily briefing workflow
  quit       — Exit (auto-saves)
""")
                continue
            elif cmd == "agents":
                print_agent_list()
                continue
            elif cmd == "session":
                print(f"\n{DIM}Session: {session_id} | User: {user_id} | Turns: {turn_count}{RESET}")
                continue
            elif cmd == "clear":
                os.system("clear" if os.name != "nt" else "cls")
                print_banner()
                continue
            elif cmd == "save":
                await save_to_memory(memory_service, session_service, session_id, user_id)
                print(f"{DIM}Session saved to memory.{RESET}")
                continue

            # Run agent turn
            turn_count += 1
            print(f"\n{CYAN}{BOLD}Assistant:{RESET} ", end="", flush=True)

            try:
                response = await run_turn(runner, session_id, user_id, user_input)
                print(response)

                # Auto-save to memory every 5 turns
                if turn_count % 5 == 0:
                    await save_to_memory(memory_service, session_service, session_id, user_id)

            except KeyboardInterrupt:
                print(f"\n{YELLOW}[Interrupted]{RESET}")
                continue
            except Exception as e:
                logger.error(f"Agent error: {e}", exc_info=True)
                print(f"\n{RED}Error: {e}{RESET}")
                print(f"{DIM}Check your GOOGLE_API_KEY and try again.{RESET}")
                continue

    except KeyboardInterrupt:
        print(f"\n\n{DIM}Saving session...{RESET}")
        await save_to_memory(memory_service, session_service, session_id, user_id)
        print(f"{DIM}Done. Goodbye!{RESET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Personal Assistant — ADK Multi-Agent Runner v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--session-id", default=None, help="Session ID to resume")
    parser.add_argument("--user-id", default=None, help="User ID for state scoping")
    parser.add_argument("--persistent", action="store_true", help="Use SQLite session persistence")
    args = parser.parse_args()

    asyncio.run(main(session_id=args.session_id, user_id=args.user_id, persistent=args.persistent))
