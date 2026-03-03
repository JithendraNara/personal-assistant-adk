"""Career Agent — job search, skill gap analysis, salary benchmarks, and interview prep."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import career_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback
from ..tools.career_tools import search_jobs, analyze_skill_gaps, get_salary_benchmark

career_agent = LlmAgent(
    name="career_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for career development, job searching, resume advice, "
        "interview preparation, and salary benchmarking. "
        "Route here for: finding job openings, analyzing skill gaps, salary research, "
        "resume feedback, interview prep questions, or career path advice."
    ),
    instruction=career_instruction_provider,
    tools=[
        search_jobs,
        analyze_skill_gaps,
        get_salary_benchmark,
        load_memory,
        PreloadMemoryTool(),
    ],
    output_key="career_last_search",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
)
