"""
Root Coordinator Agent — ADK entrypoint.

Architecture (v2 — OpenClaw-inspired):
  root_agent (LlmAgent / Coordinator)
  ├── research_agent       — web search, news, summarization
  ├── data_agent          — CSV analysis, SQL generation
  ├── career_agent        — job search, skills, salary
  ├── finance_agent       — budgeting, stocks, portfolio
  ├── sports_agent        — NFL, Cricket, F1
  ├── scheduler_agent     — tasks, planning, reminders
  ├── tech_agent          — code review, tech advice
  ├── daily_briefing      — SequentialAgent workflow
  └── info_gatherer       — ParallelAgent for concurrent fetches

Callbacks: before_agent, after_agent, before_model, after_model, before_tool, after_tool
Identity: Loaded from workspace/ markdown files at session start
Memory: PreloadMemoryTool + auto-save via after_agent_callback
"""

from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from .shared.config import DEFAULT_MODEL
from .shared.prompts import root_instruction_provider
from .shared.callbacks import (
    before_agent_callback, after_agent_callback,
    before_model_callback, after_model_callback,
)

# Import all specialist agents
from .agents.research_agent import research_agent
from .agents.data_agent import data_agent
from .agents.career_agent import career_agent
from .agents.finance_agent import finance_agent
from .agents.sports_agent import sports_agent
from .agents.scheduler_agent import scheduler_agent
from .agents.tech_agent import tech_agent

# ─── Workflow Agents ────────────────────────────────────────────────────────────────────

# Daily Briefing: Sequential pipeline that gathers info in order
# Weather → Tasks → News → Compose summary
briefing_weather = LlmAgent(
    name="briefing_weather",
    model=DEFAULT_MODEL,
    instruction="Fetch today's weather for Fort Wayne, IN. Be brief — just temperature, conditions, and any alerts.",
    output_key="briefing_weather",
    description="Fetches weather for daily briefing.",
)

briefing_tasks = LlmAgent(
    name="briefing_tasks",
    model=DEFAULT_MODEL,
    instruction="List the user's current tasks and reminders from state. Reference {scheduler_tasks?} and {scheduler_reminders?}. Summarize what's due today.",
    output_key="briefing_tasks",
    description="Summarizes today's tasks for daily briefing.",
)

briefing_news = LlmAgent(
    name="briefing_news",
    model=DEFAULT_MODEL,
    instruction="Provide 3-5 brief headlines relevant to the user: tech news, Dallas Cowboys updates, India cricket, and F1 news.",
    output_key="briefing_news",
    description="Fetches relevant news headlines for daily briefing.",
)

briefing_composer = LlmAgent(
    name="briefing_composer",
    model=DEFAULT_MODEL,
    instruction="""Compose a concise daily briefing from these sections:
- Weather: {briefing_weather?}
- Tasks: {briefing_tasks?}
- News: {briefing_news?}

Format it as a clean morning briefing. Be concise.""",
    output_key="daily_briefing_result",
    description="Composes the final daily briefing from gathered data.",
)

daily_briefing = SequentialAgent(
    name="daily_briefing",
    description=(
        "A sequential workflow that produces a personalized daily briefing. "
        "Route here when the user says 'morning briefing', 'daily update', 'what's my day look like', etc."
    ),
    sub_agents=[briefing_weather, briefing_tasks, briefing_news, briefing_composer],
)

# Parallel Info Gatherer: Fetches multiple data sources concurrently
parallel_weather = LlmAgent(
    name="parallel_weather",
    model=DEFAULT_MODEL,
    instruction="Get current weather for Fort Wayne, IN.",
    output_key="gathered_weather",
    description="Parallel weather fetch.",
)

parallel_sports = LlmAgent(
    name="parallel_sports",
    model=DEFAULT_MODEL,
    instruction="Get latest scores for Dallas Cowboys (NFL), India cricket, and F1 standings.",
    output_key="gathered_sports",
    description="Parallel sports fetch.",
)

parallel_finance = LlmAgent(
    name="parallel_finance",
    model=DEFAULT_MODEL,
    instruction="Get major market indices (S&P 500, NASDAQ) and any notable market news.",
    output_key="gathered_finance",
    description="Parallel finance fetch.",
)

info_gatherer = ParallelAgent(
    name="info_gatherer",
    description=(
        "Fetches weather, sports, and finance data concurrently. "
        "Route here when the user wants a broad update across multiple topics at once."
    ),
    sub_agents=[parallel_weather, parallel_sports, parallel_finance],
)


# ─── Root Coordinator ───────────────────────────────────────────────────────────────────────

root_agent = LlmAgent(
    name="personal_assistant",
    model=DEFAULT_MODEL,
    description=(
        "A personal assistant coordinator that routes requests to specialized agents "
        "for research, data analysis, career guidance, personal finance, sports updates, "
        "task management, software engineering help, daily briefings, and parallel info gathering."
    ),
    instruction=root_instruction_provider,  # Callable InstructionProvider
    sub_agents=[
        research_agent,
        data_agent,
        career_agent,
        finance_agent,
        sports_agent,
        scheduler_agent,
        tech_agent,
        daily_briefing,
        info_gatherer,
    ],
    tools=[
        load_memory,
        PreloadMemoryTool(),
    ],
    # ─── Callbacks (OpenClaw-inspired middleware pipeline) ─────────────────────────────────
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
)
