"""Sports Agent — NFL, Cricket, and F1 scores, standings, and news."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import sports_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback
from ..tools.sports_tools import (
    get_nfl_scores,
    get_nfl_standings,
    get_f1_standings,
    get_cricket_scores,
)

sports_agent = LlmAgent(
    name="sports_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for sports news, scores, and standings across NFL, Cricket, and Formula 1. "
        "Route here for: NFL game scores, NFL standings, Dallas Cowboys updates, "
        "Cricket match results (India team), F1 race results, F1 championship standings, "
        "or any sports-related queries."
    ),
    instruction=sports_instruction_provider,
    tools=[
        get_nfl_scores,
        get_nfl_standings,
        get_f1_standings,
        get_cricket_scores,
        load_memory,
        PreloadMemoryTool(),
    ],
    output_key="sports_last_update",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
)
