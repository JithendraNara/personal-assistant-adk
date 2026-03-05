"""
Standalone MCP Server for UnifiedMemory.

Exposes memory operations to Claude Code (and other MCP clients)
by proxying requests to the live DigitalOcean UnifiedMemory API.

Usage:
    python mcp_server.py                  # Run as stdio server
    python mcp_server.py --transport sse  # Run as SSE server (HTTP)
"""
import asyncio
import json
import os
import sys
import argparse
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

# Optionally override these via environment variables in Claude's settings.json
API_URL = os.environ.get("UM_API_URL", "http://64.227.16.66:8000/api/v1")
API_KEY = os.environ.get("UM_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MCP] %(message)s")
logger = logging.getLogger(__name__)

# ─── API Client Helpers ──────────────────────────────────────────────────────

def _make_request(endpoint: str, method: str = "GET", data: Optional[dict] = None) -> dict:
    """"Helper to make HTTP requests to the UnifiedMemory API."""
    url = f"{API_URL}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            body = response.read().decode("utf-8")
            if body:
                return json.loads(body)
            return {"status": "success"}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error(f"UM API Error {e.code}: {error_body}")
        raise RuntimeError(f"API Error {e.code}: {error_body}")
    except Exception as e:
        logger.error(f"UM API Connection Error: {e}")
        raise RuntimeError(f"Connection Error: {e}")


# ─── MCP Server ──────────────────────────────────────────────────────────────

def create_mcp_server():
    from mcp.server.lowlevel import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.types as mcp_types
    from pydantic import Field

    app = Server("unified-memory-mcp")

    @app.list_tools()
    async def list_mcp_tools() -> list[mcp_types.Tool]:
        """Advertise UnifiedMemory tools to MCP clients."""
        return [
            mcp_types.Tool(
                name="um_add_memory",
                description="Store a new fact, instruction, or context in long-term UnifiedMemory.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The information to remember."
                        },
                        "container_tag": {
                            "type": "string",
                            "description": "Optional category tag (e.g., 'workspace', 'rules', 'preferences')."
                        }
                    },
                    "required": ["content"]
                }
            ),
            mcp_types.Tool(
                name="um_search_memory",
                description="Search long-term UnifiedMemory for relevant past context using semantic search.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question or topic to search for."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 5)."
                        }
                    },
                    "required": ["query"]
                }
            ),
            mcp_types.Tool(
                name="um_get_profile",
                description="Retrieve the synthesized AI profile of the user based on all their memories.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            )
        ]

    @app.call_tool()
    async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
        """Execute a tool call from an MCP client."""
        logger.info(f"MCP: call_tool '{name}' with args: {arguments}")

        try:
            if name == "um_add_memory":
                response = _make_request(
                    "memories", 
                    method="POST", 
                    data={
                        "content": arguments["content"],
                        "container_tag": arguments.get("container_tag", "jeethendra"),
                        "auto_extract": True
                    }
                )
                return [mcp_types.TextContent(type="text", text=f"Successfully stored memory. ID: {response.get('id', 'unknown')}")]
                
            elif name == "um_search_memory":
                limit = arguments.get("limit", 5)
                response = _make_request(
                    "memories/search", 
                    method="POST",
                    data={
                        "query": arguments["query"],
                        "limit": limit,
                        "container_tag": "jeethendra"
                    }
                )
                
                results = response.get("results", [])
                if not results or len(results) == 0:
                     return [mcp_types.TextContent(type="text", text="No relevant memories found.")]
                     
                formatted_results = []
                for idx, result in enumerate(results):
                    score = result.get('score', 0.0)
                    formatted_results.append(f"{idx+1}. {result.get('content', '')} (Confidence: {score:.2f})")
                    
                final_text = "Found the following relevant memories:\n\n" + "\n".join(formatted_results)
                return [mcp_types.TextContent(type="text", text=final_text)]
                
            elif name == "um_get_profile":
                response = _make_request("profile/jeethendra", method="GET")
                return [mcp_types.TextContent(type="text", text=json.dumps(response, indent=2))]
                
            else:
                return [mcp_types.TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            logger.error(f"MCP: Tool '{name}' failed: {e}")
            return [mcp_types.TextContent(type="text", text=f"Error: {e}")]

    return app


# ─── Server Runners ──────────────────────────────────────────────────────────

async def run_stdio_server():
    """Run MCP server using stdio transport (for local tools)."""
    import mcp.server.stdio
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions

    app = create_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
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


async def run_sse_server(host: str, port: int):
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

    config = uvicorn.Config(starlette_app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UnifiedMemory MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()

    try:
        if args.transport == "sse":
            asyncio.run(run_sse_server(host=args.host, port=args.port))
        else:
            asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        pass
