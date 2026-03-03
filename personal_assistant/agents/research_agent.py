"""Research Agent — web search, summarization, news, and fact-finding."""

from google.adk.agents import LlmAgent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from ..shared.config import DEFAULT_MODEL
from ..shared.prompts import research_instruction_provider
from ..shared.callbacks import before_tool_callback, after_tool_callback
from ..tools.web_tools import web_search, fetch_webpage_summary, get_news_headlines, summarize_text

research_agent = LlmAgent(
    name="research_agent",
    model=DEFAULT_MODEL,
    description=(
        "Specialist for web research, news aggregation, summarization, and fact-finding. "
        "Route here for: searching the web, getting news headlines, reading and summarizing URLs, "
        "or any research and information gathering tasks."
    ),
    instruction=research_instruction_provider,
    tools=[
        web_search,
        fetch_webpage_summary,
        get_news_headlines,
        summarize_text,
        load_memory,
        PreloadMemoryTool(),
    ],
    output_key="research_last_topic",
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
)
