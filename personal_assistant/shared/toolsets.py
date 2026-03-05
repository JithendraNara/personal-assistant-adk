"""
Optional ADK toolset builders (MCP / OpenAPI), driven by environment variables.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _agent_enabled(agent_name: str, env_name: str, default_agents: list[str]) -> bool:
    configured = _env_list(env_name)
    if not configured:
        configured = default_agents
    return "*" in configured or agent_name in configured


def _parse_args(raw_args: str) -> list[str]:
    if not raw_args.strip():
        return []
    trimmed = raw_args.strip()
    if trimmed.startswith("["):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list) and all(isinstance(v, str) for v in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
    return shlex.split(trimmed)


def _parse_env_json(raw: str) -> dict[str, str] | None:
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid JSON in MCP_SERVER_ENV_JSON")
        return None
    if not isinstance(parsed, dict):
        logger.warning("Ignoring MCP_SERVER_ENV_JSON because it is not an object")
        return None
    out: dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out or None


def build_optional_toolsets(agent_name: str) -> list[Any]:
    """
    Build optional ADK toolsets for an agent.

    Env vars:
      MCP_SERVER_COMMAND, MCP_SERVER_ARGS, MCP_SERVER_CWD, MCP_SERVER_ENV_JSON, MCP_AGENTS
      OPENAPI_SPEC_PATH, OPENAPI_SPEC_URL, OPENAPI_SPEC_JSON, OPENAPI_SPEC_TYPE, OPENAPI_AGENTS
      OPENAPI_TOOL_NAME_PREFIX
    """
    toolsets: list[Any] = []
    toolsets.extend(_build_builtin_integration_tools(agent_name))
    toolsets.extend(_build_mcp_toolsets(agent_name))
    toolsets.extend(_build_openapi_toolsets(agent_name))
    return toolsets


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_builtin_integration_tools(agent_name: str) -> list[Any]:
    """
    Built-in ADK integrations exposed as tools.
    """
    tools: list[Any] = []

    if _is_true(os.getenv("ENABLE_GOOGLE_SEARCH_TOOL")) and _agent_enabled(
        agent_name,
        "GOOGLE_SEARCH_AGENTS",
        ["research_agent", "personal_assistant"],
    ):
        try:
            from google.adk.tools import google_search

            tools.append(google_search)
        except Exception as exc:
            logger.warning("Failed enabling google_search tool: %s", exc)

    return tools


def _build_mcp_toolsets(agent_name: str) -> list[Any]:
    if not _agent_enabled(
        agent_name, "MCP_AGENTS", ["research_agent", "data_agent", "tech_agent", "personal_assistant"]
    ):
        return []

    command = os.getenv("MCP_SERVER_COMMAND", "").strip()
    if not command:
        return []

    args = _parse_args(os.getenv("MCP_SERVER_ARGS", ""))
    cwd = os.getenv("MCP_SERVER_CWD", "").strip() or None
    env_dict = _parse_env_json(os.getenv("MCP_SERVER_ENV_JSON", ""))

    try:
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

        params = StdioServerParameters(
            command=command,
            args=args,
            cwd=cwd,
            env=env_dict,
        )
        return [MCPToolset(connection_params=params)]
    except Exception as exc:
        logger.warning("Failed to initialize MCPToolset: %s", exc)
        return []


def _build_openapi_toolsets(agent_name: str) -> list[Any]:
    if not _agent_enabled(
        agent_name, "OPENAPI_AGENTS", ["research_agent", "data_agent", "tech_agent", "personal_assistant"]
    ):
        return []

    spec_json = os.getenv("OPENAPI_SPEC_JSON", "").strip()
    spec_path = os.getenv("OPENAPI_SPEC_PATH", "").strip()
    spec_url = os.getenv("OPENAPI_SPEC_URL", "").strip()
    spec_type = os.getenv("OPENAPI_SPEC_TYPE", "json").strip().lower() or "json"
    if spec_type not in {"json", "yaml"}:
        spec_type = "json"
    tool_name_prefix = os.getenv("OPENAPI_TOOL_NAME_PREFIX", "").strip() or None

    openapi_kwargs: dict[str, Any] = {}
    if tool_name_prefix:
        openapi_kwargs["tool_name_prefix"] = tool_name_prefix

    try:
        from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
    except Exception as exc:
        logger.warning("OpenAPIToolset import failed: %s", exc)
        return []

    if spec_json:
        try:
            spec_dict = json.loads(spec_json)
        except json.JSONDecodeError:
            logger.warning("Ignoring OPENAPI_SPEC_JSON because it is invalid JSON")
            return []
        return [OpenAPIToolset(spec_dict=spec_dict, **openapi_kwargs)]

    if spec_path:
        path = Path(spec_path)
        if not path.exists():
            logger.warning("OPENAPI_SPEC_PATH does not exist: %s", spec_path)
            return []
        content = path.read_text(encoding="utf-8")
        inferred_type = "yaml" if path.suffix.lower() in {".yaml", ".yml"} else spec_type
        return [OpenAPIToolset(spec_str=content, spec_str_type=inferred_type, **openapi_kwargs)]

    if spec_url:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(spec_url)
                response.raise_for_status()
                content = response.text
        except Exception as exc:
            logger.warning("Failed fetching OPENAPI_SPEC_URL (%s): %s", spec_url, exc)
            return []
        return [OpenAPIToolset(spec_str=content, spec_str_type=spec_type, **openapi_kwargs)]

    return []
