"""
Tools package — function tools used by specialist agents.

Each module exports plain Python functions that are registered as
ADK FunctionTools when passed to an agent's tools=[...] list.
"""

from . import web_tools, data_tools, career_tools, finance_tools
from . import sports_tools, scheduler_tools, tech_tools

__all__ = [
    "web_tools",
    "data_tools",
    "career_tools",
    "finance_tools",
    "sports_tools",
    "scheduler_tools",
    "tech_tools",
]
