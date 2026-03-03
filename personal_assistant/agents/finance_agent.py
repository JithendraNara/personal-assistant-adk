"""Finance Agent — personal finance, budgeting, investment analysis, and portfolio review."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import finance_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback
from ..tools.finance_tools import (
    calculate_budget,
    get_stock_quote,
    analyze_investment_portfolio,
)

finance_agent = LlmAgent(
    name="finance_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for personal finance, budgeting analysis, investment portfolio review, "
        "and stock/ETF quotes. "
        "Route here for: budget breakdowns, savings analysis, stock price lookups, "
        "portfolio diversification checks, investment recommendations, or expense optimization."
    ),
    instruction=finance_instruction_provider,
    tools=[
        calculate_budget,
        get_stock_quote,
        analyze_investment_portfolio,
        load_memory,
        PreloadMemoryTool(),
    ],
    output_key="finance_last_check",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
)
