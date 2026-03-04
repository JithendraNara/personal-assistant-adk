#!/usr/bin/env python3
"""
UnifiedMemory — Standalone Launcher.

Run this to start the memory dashboard + API without
needing the full ADK stack installed.

Usage:
    python memory_app.py              # Dashboard + API on port 8082
    python memory_app.py --port 3000  # Custom port
"""

import asyncio
import sys
import os
import logging

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Prevent personal_assistant/__init__.py from importing google.adk
# by pre-registering the package as a bare namespace
import types
pkg = types.ModuleType("personal_assistant")
pkg.__path__ = [os.path.join(os.path.dirname(__file__), "personal_assistant")]
pkg.__package__ = "personal_assistant"
sys.modules["personal_assistant"] = pkg

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Memory] %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UnifiedMemory — Dashboard + API")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8082, help="Port (default: 8082)")
    args = parser.parse_args()

    # Import after path setup
    from personal_assistant.memory.server import create_rest_app
    import uvicorn

    app = create_rest_app()

    print()
    print("  🧠 UnifiedMemory is running!")
    print()
    print(f"  Dashboard:  http://localhost:{args.port}")
    print(f"  API Docs:   http://localhost:{args.port}/docs")
    print(f"  Stats:      http://localhost:{args.port}/memories/stats")
    print(f"  Profile:    http://localhost:{args.port}/memories/profile/jeethendra")
    print()
    print("  Connect your AI tools → http://localhost:%d (Connect page)" % args.port)
    print()

    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("\n\n  🧠 UnifiedMemory stopped. Your memories are safe at ~/.unified-memory/\n")


if __name__ == "__main__":
    main()
