"""Data Agent — CSV analysis, SQL generation, data profiling, and visualization advice."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import data_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback
from ..tools.data_tools import (
    profile_csv,
    generate_sql_query,
    analyze_dataframe_from_csv,
    describe_data_for_visualization,
)

data_agent = LlmAgent(
    name="data_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for data analysis, CSV profiling, SQL query generation, "
        "and data visualization recommendations. "
        "Route here for: analyzing CSV files, writing SQL queries (BigQuery/Postgres/Snowflake), "
        "data profiling, pandas code generation, or chart/viz recommendations."
    ),
    instruction=data_instruction_provider,
    tools=[
        profile_csv,
        generate_sql_query,
        analyze_dataframe_from_csv,
        describe_data_for_visualization,
        load_memory,
        PreloadMemoryTool(),
    ],
    output_key="data_last_analysis",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
)
