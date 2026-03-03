"""
Personal Assistant — Google ADK Multi-Agent Ecosystem.

A production-quality, OpenClaw-inspired personal assistant built on the
Google Agent Development Kit (ADK). Features:
- Workspace-based identity system (SOUL.md, USER.md, AGENTS.md)
- Full callback pipeline (guardrails, logging, memory, session lifecycle)
- Workflow orchestration (Sequential, Parallel, Loop agents)
- Agent-to-agent communication via AgentTool and shared state
- MCP tool integration for extensibility
- Persistent sessions and memory
"""

from .agent import root_agent

__all__ = ["root_agent"]
