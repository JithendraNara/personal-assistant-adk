"""
Personal Assistant — Google ADK Multi-Agent Ecosystem.

A production-quality, OpenClaw-inspired personal assistant built on the
Google Agent Development Kit (ADK). Features:
- Workspace-based identity system (SOUL.md, USER.md, AGENTS.md)
- Full callback pipeline (guardrails, logging, memory, session lifecycle)
- Workflow orchestration (Sequential + Parallel workflows)
- ADK App runtime (plugins, resumability, optional context cache/compaction)
- Optional MCP/OpenAPI toolset integration (env-driven)
- Persistent sessions, memory, and artifact backends
"""

from .agent import root_agent

__all__ = ["root_agent"]
