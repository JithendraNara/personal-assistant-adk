#!/usr/bin/env python3
"""
Standalone MCP smoke test.

Usage:
    python test_mcp.py
"""

import asyncio

from mcp import types as mcp_types

from mcp_server import create_mcp_server


async def run_mcp_smoke() -> int:
    app = create_mcp_server()

    list_handler = app.request_handlers.get(mcp_types.ListToolsRequest)
    if not list_handler:
        print("Failed: MCP list_tools handler is not registered")
        return 1

    result = await list_handler(
        mcp_types.ListToolsRequest(
            method="tools/list",
            params=mcp_types.PaginatedRequestParams(),
        )
    )

    tools = result.root.tools if hasattr(result.root, "tools") else []
    tool_names = [tool.name for tool in tools]
    print("Registered MCP tools:", ", ".join(tool_names) if tool_names else "[none]")

    expected = {"um_add_memory", "um_search_memory", "um_get_profile"}
    missing = sorted(expected - set(tool_names))
    if missing:
        print("Failed: missing tools:", ", ".join(missing))
        return 1

    print("MCP smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_mcp_smoke()))
