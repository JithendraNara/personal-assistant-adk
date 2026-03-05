"""
UnifiedMemory — MCP + REST Server for cross-platform memory sync.

Exposes the memory engine as both:
  1. MCP tools (for Claude, Cursor, Codex, etc.)
  2. REST API (for ADK, OpenClaw, custom integrations)

MCP Tools:
  - save_memory: Store important information
  - recall: Search memories for relevant context
  - get_profile: Get user profile with static + dynamic context
  - forget: Remove a specific memory

REST API:
  - POST /memories — add memories
  - POST /memories/search — search memories
  - GET /memories/profile/{tag} — get user profile
  - GET /memories/stats — memory statistics
  - DELETE /memories/{id} — forget a memory

Usage:
    python -m personal_assistant.memory.server                  # stdio MCP
    python -m personal_assistant.memory.server --transport rest  # REST API (port 8082)
"""

import asyncio
import json
import os
import argparse
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


# ─── MCP Server ──────────────────────────────────────────────────────────────

def create_memory_mcp_server():
    """Create MCP server with memory tools."""
    from mcp import types as mcp_types
    from mcp.server.lowlevel import Server
    from personal_assistant.memory.engine import UnifiedMemoryEngine

    app = Server("unified-memory-mcp")
    engine = UnifiedMemoryEngine()

    @app.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="save_memory",
                description=(
                    "Save important information to long-term memory. "
                    "Use this to remember facts, preferences, project context, "
                    "and anything the user would want you to know in future conversations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The information to remember. Can be a fact, preference, or conversation excerpt.",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags for categorization.",
                        },
                    },
                    "required": ["content"],
                },
            ),
            mcp_types.Tool(
                name="recall",
                description=(
                    "Search memories for relevant context. "
                    "Use this to find what you know about the user, their projects, "
                    "preferences, or any previously stored information."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for in memory.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            mcp_types.Tool(
                name="get_profile",
                description=(
                    "Get the user's profile with long-term facts and current context. "
                    "Returns static facts (persistent) and dynamic context (recent activity)."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            mcp_types.Tool(
                name="forget",
                description="Remove a specific memory by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string", "description": "ID of the memory to forget."},
                    },
                    "required": ["memory_id"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
        container_tag = os.getenv("MEMORY_CONTAINER_TAG", "jeethendra")

        if name == "save_memory":
            memories = await engine.add(
                content=arguments["content"],
                container_tag=container_tag,
                source="mcp",
                auto_extract=True,
            )
            result = {
                "saved": len(memories),
                "memories": [{"id": m.id, "content": m.content, "type": m.memory_type.value} for m in memories],
            }
            return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "recall":
            results = await engine.search(
                query=arguments["query"],
                container_tag=container_tag,
                limit=arguments.get("limit", 5),
            )
            output = [{
                "content": r.memory.content,
                "type": r.memory.memory_type.value,
                "score": round(r.score, 3),
                "source": r.memory.source,
                "date": r.memory.updated_at.strftime("%Y-%m-%d"),
            } for r in results]
            return [mcp_types.TextContent(type="text", text=json.dumps(output, indent=2))]

        elif name == "get_profile":
            profile = await engine.profile(container_tag)
            return [mcp_types.TextContent(type="text", text=json.dumps(profile.to_dict(), indent=2))]

        elif name == "forget":
            success = await engine.forget(arguments["memory_id"])
            return [mcp_types.TextContent(
                type="text",
                text=json.dumps({"forgotten": success, "id": arguments["memory_id"]}),
            )]

        return [mcp_types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    return app


# ─── REST API ────────────────────────────────────────────────────────────────

def create_rest_app():
    """Create FastAPI REST app with dashboard UI and memory API."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
    from personal_assistant.memory.engine import UnifiedMemoryEngine

    app = FastAPI(
        title="UnifiedMemory API",
        version="1.0.0",
        description="Cross-platform memory for all your AI agents. One brain, everywhere.",
    )

    # Serve dashboard at root
    DASHBOARD_DIR = Path(__file__).parent / "dashboard"

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the UnifiedMemory dashboard."""
        index = DASHBOARD_DIR / "index.html"
        if index.exists():
            return HTMLResponse(content=index.read_text(), status_code=200)
        return HTMLResponse(content="<h1>UnifiedMemory</h1><p>Dashboard not found. Check /docs for API.</p>")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    engine = UnifiedMemoryEngine()

    class AddRequest(BaseModel):
        content: str
        container_tag: str = "default"
        source: str = "rest"
        auto_extract: bool = True

    class SearchRequest(BaseModel):
        query: str
        container_tag: str = "default"
        limit: int = 10
        mode: str = "hybrid"

    @app.post("/memories")
    async def add_memories(req: AddRequest):
        memories = await engine.add(
            content=req.content,
            container_tag=req.container_tag,
            source=req.source,
            auto_extract=req.auto_extract,
        )
        return {
            "saved": len(memories),
            "memories": [m.to_dict() for m in memories],
        }

    @app.post("/memories/search")
    async def search_memories(req: SearchRequest):
        results = await engine.search(
            query=req.query,
            container_tag=req.container_tag,
            limit=req.limit,
            mode=req.mode,
        )
        return {
            "results": [{
                "memory": r.memory.to_dict(),
                "score": round(r.score, 3),
                "match_type": r.match_type,
            } for r in results],
        }

    @app.get("/memories/profile/{container_tag}")
    async def get_profile(container_tag: str):
        profile = await engine.profile(container_tag)
        return profile.to_dict()

    @app.get("/memories/stats")
    async def get_stats(container_tag: str = "default"):
        return engine.sync_stats()

    @app.delete("/memories/{memory_id}")
    async def forget_memory(memory_id: str):
        success = await engine.forget(memory_id)
        return {"forgotten": success}

    @app.get("/memories/config")
    async def get_config():
        """Generate MCP client configs for cross-platform setup."""
        base_url = os.getenv("MEMORY_BASE_URL", "http://localhost:8082")
        return {
            "instructions": "Add the 'supermemory' config to your MCP client settings.",
            "clients": {
                "claude_desktop": {
                    "mcpServers": {
                        "unified-memory": {
                            "command": "python",
                            "args": ["-m", "personal_assistant.memory.server"],
                        }
                    }
                },
                "cursor": {
                    "mcpServers": {
                        "unified-memory": {
                            "command": "python",
                            "args": ["-m", "personal_assistant.memory.server"],
                        }
                    }
                },
                "rest_api": {
                    "base_url": base_url,
                    "endpoints": {
                        "add": "POST /memories",
                        "search": "POST /memories/search",
                        "profile": "GET /memories/profile/{tag}",
                        "stats": "GET /memories/stats",
                    }
                },
            },
        }

    return app


# ─── Runners ─────────────────────────────────────────────────────────────────

async def run_stdio():
    """Run memory MCP server via stdio."""
    import mcp.server.stdio
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions

    app = create_memory_mcp_server()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name="unified-memory",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


async def run_rest(host: str = "127.0.0.1", port: int = 8082):
    """Run memory REST API + dashboard server."""
    import uvicorn
    app = create_rest_app()
    logger.info("")
    logger.info("  🧠 UnifiedMemory is running!")
    logger.info("")
    logger.info(f"  Dashboard:  http://localhost:{port}")
    logger.info(f"  API Docs:   http://localhost:{port}/docs")
    logger.info(f"  Stats:      http://localhost:{port}/memories/stats")
    logger.info("")
    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [Memory] %(message)s")

    parser = argparse.ArgumentParser(description="UnifiedMemory Server")
    parser.add_argument(
        "--transport", choices=["stdio", "rest"], default="stdio",
        help="Transport: stdio (MCP) or rest (HTTP API)",
    )
    parser.add_argument("--host", default=os.getenv("MEMORY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=8082)
    args = parser.parse_args()

    try:
        if args.transport == "rest":
            asyncio.run(run_rest(host=args.host, port=args.port))
        else:
            asyncio.run(run_stdio())
    except KeyboardInterrupt:
        print("\nMemory server stopped.")
