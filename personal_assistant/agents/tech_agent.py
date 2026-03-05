"""Tech Agent — code review, debugging, tech comparisons, streaming setup, cloud/infra advice."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import tech_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback, on_tool_error_callback
from ..shared.skills import build_skill_toolsets
from ..tools.tech_tools import (
    analyze_code,
    compare_tech_options,
    get_streaming_setup_advice,
)

tech_agent = LlmAgent(
    name="tech_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for software engineering, code review, debugging, technology comparisons, "
        "streaming device setup, cloud infrastructure, and general tech recommendations. "
        "Route here for: code review or debugging, choosing between frameworks/tools, "
        "Python/Node.js/Terraform help, Apple TV or streaming device setup, "
        "cloud architecture questions (AWS/GCP/Azure), or Linux tips."
    ),
    instruction=tech_instruction_provider,
    tools=[
        analyze_code,
        compare_tech_options,
        get_streaming_setup_advice,
        load_memory,
        PreloadMemoryTool(),
        *build_skill_toolsets("tech_agent"),
    ],
    output_key="tech_last_query",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    on_tool_error_callback=on_tool_error_callback,
)
