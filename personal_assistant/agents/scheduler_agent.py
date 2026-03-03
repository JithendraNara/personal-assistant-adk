"""Scheduler Agent — task management, daily planning, and reminder setting."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import scheduler_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback
from ..tools.scheduler_tools import (
    create_task,
    list_tasks,
    update_task_status,
    build_daily_plan,
    set_reminder,
)

scheduler_agent = LlmAgent(
    name="scheduler_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for task management, daily planning, reminders, and productivity. "
        "Route here for: creating or listing tasks, building a daily agenda, "
        "setting reminders, prioritizing work, or weekly planning."
    ),
    instruction=scheduler_instruction_provider,
    tools=[
        create_task,
        list_tasks,
        update_task_status,
        build_daily_plan,
        set_reminder,
        load_memory,
        PreloadMemoryTool(),
    ],
    output_key="scheduler_last_tasks",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
)
