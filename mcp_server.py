"""
MCP Server — expose Personal Assistant tools as MCP-compatible tools.

This allows any MCP-compatible client to discover and use our tools.
Built following ADK's official MCP tool integration pattern:
  google.adk.tools.mcp_tool.conversion_utils.adk_to_mcp_tool_type

Usage:
    python mcp_server.py                  # Run as stdio server
    python mcp_server.py --transport sse  # Run as SSE server (HTTP)

Requires:
    pip install mcp
"""

import asyncio
import json
import os
import argparse
import logging

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ─── Tool Registry ───────────────────────────────────────────────────────────
# All tools that should be exposed via MCP

def _get_exposed_tools():
    """
    Collect all tools to expose via MCP.
    Uses lazy imports to avoid heavy startup cost.
    """
    from google.adk.tools.function_tool import FunctionTool

    # Import all tool functions
    from personal_assistant.tools.web_tools import (
        web_search, fetch_webpage_summary, get_news_headlines,
    )
    from personal_assistant.tools.scheduler_tools import (
        create_task, list_tasks, update_task_status,
        build_daily_plan, set_reminder,
    )
    from personal_assistant.tools.finance_tools import (
        get_stock_quote, analyze_budget, calculate_compound_interest,
    )
    from personal_assistant.tools.career_tools import (
        search_jobs, analyze_skill_gaps,
    )
    from personal_assistant.tools.sports_tools import (
        get_nfl_scores, get_f1_standings, get_cricket_scores,
    )
    from personal_assistant.tools.data_tools import (
        profile_csv, generate_sql_query,
    )

    tools = {
        # Web tools
        "web_search": FunctionTool(web_search),
        "fetch_webpage_summary": FunctionTool(fetch_webpage_summary),
        "get_news_headlines": FunctionTool(get_news_headlines),
        # Scheduler tools
        "create_task": FunctionTool(create_task),
        "list_tasks": FunctionTool(list_tasks),
        "update_task_status": FunctionTool(update_task_status),
        "build_daily_plan": FunctionTool(build_daily_plan),
        "set_reminder": FunctionTool(set_reminder),
        # Finance tools
        "get_stock_quote": FunctionTool(get_stock_quote),
        "analyze_budget": FunctionTool(analyze_budget),
        "calculate_compound_interest": FunctionTool(calculate_compound_interest),
        # Career tools
        "search_jobs": FunctionTool(search_jobs),
        "analyze_skill_gaps": FunctionTool(analyze_skill_gaps),
        # Sports tools
        "get_nfl_scores": FunctionTool(get_nfl_scores),
        "get_f1_standings": FunctionTool(get_f1_standings),
        "get_cricket_scores": FunctionTool(get_cricket_scores),
        # Data tools
        "profile_csv": FunctionTool(profile_csv),
        "generate_sql_query": FunctionTool(generate_sql_query),
    }
    return tools


# ─── MCP Server ──────────────────────────────────────────────────────────────

def create_mcp_server():
    """Create and configure the MCP server with all exposed tools."""
    from mcp import types as mcp_types
    from mcp.server.lowlevel import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

    app = Server("personal-assistant-mcp-server")
    tools = _get_exposed_tools()

    @app.list_tools()
    async def list_mcp_tools() -> list[mcp_types.Tool]:
        """Advertise all tools to MCP clients."""
        logger.info(f"MCP: Listing {len(tools)} tools")
        return [adk_to_mcp_tool_type(tool) for tool in tools.values()]

    @app.call_tool()
    async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
        """Execute a tool call from an MCP client."""
        logger.info(f"MCP: call_tool '{name}' with args: {list(arguments.keys())}")

        tool = tools.get(name)
        if not tool:
            error = json.dumps({"error": f"Tool '{name}' not found. Available: {list(tools.keys())}"})
            return [mcp_types.TextContent(type="text", text=error)]

        try:
            # Execute ADK tool (tool_context=None since running outside ADK Runner)
            result = await tool.run_async(args=arguments, tool_context=None)
            response_text = json.dumps(result, indent=2, default=str)
            return [mcp_types.TextContent(type="text", text=response_text)]
        except Exception as e:
            logger.error(f"MCP: Tool '{name}' failed: {e}")
            error = json.dumps({"error": f"Tool execution failed: {str(e)}"})
            return [mcp_types.TextContent(type="text", text=error)]

    return app


# ─── Server Runners ──────────────────────────────────────────────────────────

async def run_stdio_server():
    """Run MCP server using stdio transport (for local tools)."""
    import mcp.server.stdio
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions

    app = create_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("MCP: Starting stdio server...")
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=app.name,
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


async def run_sse_server(host: str = "0.0.0.0", port: int = 8081):
    """Run MCP server using SSE transport (for remote HTTP access)."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route
    import uvicorn

    app = create_mcp_server()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(
                streams[0],
                streams[1],
                app.create_initialization_options(),
            )

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages/", endpoint=sse.handle_post_message, methods=["POST"]),
        ],
    )

    logger.info(f"MCP: Starting SSE server on {host}:{port}")
    config = uvicorn.Config(starlette_app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [MCP] %(message)s")

    parser = argparse.ArgumentParser(description="Personal Assistant MCP Server")
    parser.add_argument(
        "--transport", choices=["stdio", "sse"], default="stdio",
        help="Transport type: stdio (local) or sse (HTTP, default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="SSE host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8081, help="SSE port (default: 8081)")
    args = parser.parse_args()

    try:
        if args.transport == "sse":
            asyncio.run(run_sse_server(host=args.host, port=args.port))
        else:
            asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        print("\nMCP Server stopped.")
