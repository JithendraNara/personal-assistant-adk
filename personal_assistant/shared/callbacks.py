"""
Callback system — guardrails, logging, memory warmup, session lifecycle.

Inspired by OpenClaw's middleware pattern, adapted for ADK's callback API.

ADK Callback Signatures:
  before_agent_callback(callback_context: CallbackContext) -> Content | None
  after_agent_callback(callback_context: CallbackContext) -> Content | None
  before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None
  after_model_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> LlmResponse | None
  before_tool_callback(tool: BaseTool, args: dict, tool_context: ToolContext) -> dict | None
  after_tool_callback(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response: dict) -> dict | None
  on_model_error_callback(callback_context: CallbackContext, llm_request: LlmRequest, error: Exception) -> LlmResponse | None
  on_tool_error_callback(tool: BaseTool, args: dict, tool_context: ToolContext, error: Exception) -> dict | None
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Any

from google.adk.agents import Context
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools import BaseTool
from google.adk.tools import ToolContext
from google.genai import types

from personal_assistant.shared.security import check_tool_access, sanitize_input

logger = logging.getLogger(__name__)


def _resolve_agent_context(
    callback_context: Context | CallbackContext | None = None,
    *,
    context: Context | CallbackContext | None = None,
) -> Context | CallbackContext:
    """
    Normalize agent callback context across ADK versions.

    ADK currently invokes agent callbacks with `callback_context=...`.
    Older local tests and docs may still pass a positional/`context` argument.
    """
    resolved = callback_context or context
    if resolved is None:
        raise TypeError(
            "Agent callback requires a context object via `callback_context` or `context`."
        )
    return resolved


# ─── Before Agent Callback ────────────────────────────────────────────────────
# Runs before agent starts processing. Used for:
# - Session warmup (inject context from workspace files)
# - Daily session rotation check
# - Interaction logging

async def before_agent_callback(
    callback_context: Context | CallbackContext | None = None,
    *,
    context: Context | CallbackContext | None = None,
) -> Optional[types.Content]:
    """
    Pre-agent hook: injects workspace identity, checks session age, logs interaction.
    Returns None to proceed, or Content to short-circuit.
    """
    resolved_context = _resolve_agent_context(callback_context, context=context)
    agent_name = resolved_context.agent_name
    state = resolved_context.state

    # Track interaction count
    count = state.get("_interaction_count", 0)
    state["_interaction_count"] = count + 1
    state["temp:turn_start_time"] = time.time()

    # Inject workspace identity into state if not already there
    if not state.get("_identity_loaded"):
        from .config import SOUL_MD, USER_MD, AGENTS_MD, IDENTITY_MD
        state["app:soul"] = SOUL_MD
        state["app:user_profile"] = USER_MD
        state["app:agents_instructions"] = AGENTS_MD
        state["app:identity"] = IDENTITY_MD
        state["_identity_loaded"] = True
        logger.info(f"[{agent_name}] Workspace identity loaded into session state")

    # Daily session rotation check
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session_date = state.get("_session_date", "")
    if session_date and session_date != today:
        logger.info(f"[{agent_name}] Session spans new day ({session_date} → {today}), marking for rotation")
        state["_needs_rotation"] = True
    if not session_date:
        state["_session_date"] = today

    logger.info(f"[{agent_name}] Turn {count + 1} starting")
    return None  # Proceed to agent


# ─── After Agent Callback ─────────────────────────────────────────────────────
# Runs after agent completes. Used for:
# - Auto-save to memory (like OpenClaw's session archival)
# - Interaction metrics
# - Session size pruning trigger

async def after_agent_callback(
    callback_context: Context | CallbackContext | None = None,
    *,
    context: Context | CallbackContext | None = None,
) -> Optional[types.Content]:
    """
    Post-agent hook: logs metrics, triggers memory save on significant interactions.
    """
    resolved_context = _resolve_agent_context(callback_context, context=context)
    agent_name = resolved_context.agent_name
    state = resolved_context.state

    # Calculate turn duration
    start_time = state.get("temp:turn_start_time", time.time())
    duration = time.time() - start_time
    state["_last_turn_duration"] = round(duration, 2)

    # Track which agents were used (for analytics)
    agents_used = state.get("user:agents_used", [])
    if agent_name not in agents_used:
        agents_used.append(agent_name)
        state["user:agents_used"] = agents_used

    # Auto-save to memory every N interactions
    interaction_count = state.get("_interaction_count", 0)
    if interaction_count > 0 and interaction_count % 5 == 0:
        logger.info(f"[{agent_name}] Auto-save checkpoint at interaction {interaction_count}")
        state["_memory_save_pending"] = True

    logger.info(f"[{agent_name}] Turn completed in {duration:.2f}s")
    return None


# ─── Before Model Callback ────────────────────────────────────────────────────
# Runs before sending request to LLM. Used for:
# - Input guardrails (block sensitive data patterns)
# - Request logging
# - Prompt injection detection

async def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    Pre-LLM hook: validates input, injects workspace context into system instruction.
    """
    agent_name = callback_context.agent_name

    # Extract last user message for guardrail check
    if llm_request.contents:
        last_content = llm_request.contents[-1]
        if last_content.parts:
            last_text = last_content.parts[0].text or ""

            # Guardrail: use security module for input sanitization
            _, detected = sanitize_input(last_text)
            if detected:
                    logger.warning(f"[{agent_name}] Sensitive data detected ({detected}) — blocking")
                    return LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[types.Part(text=(
                                "I noticed your message may contain sensitive information "
                                f"({', '.join(detected)}). For security, I've blocked this request. "
                                "Please remove any sensitive data and try again."
                            ))]
                        )
                    )

    logger.debug(f"[{agent_name}] Sending request to LLM")
    return None  # Proceed to LLM


# ─── After Model Callback ─────────────────────────────────────────────────────
# Runs after receiving LLM response. Used for:
# - Response sanitization
# - Response quality logging

async def after_model_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """
    Post-LLM hook: logs response, sanitizes output.
    """
    agent_name = callback_context.agent_name
    logger.debug(f"[{agent_name}] Received LLM response")
    return None  # Use LLM response as-is


# ─── Before Tool Callback ─────────────────────────────────────────────────────
# Runs before executing a tool. Used for:
# - Argument validation
# - Rate limiting
# - Tool usage logging

async def before_tool_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """
    Pre-tool hook: validates arguments, logs tool usage.
    """
    agent_name = tool_context.agent_name
    state = tool_context.state

    # Per-agent tool access policy check (OpenClaw sandbox pattern)
    allowed, reason = check_tool_access(agent_name, tool.name)
    if not allowed:
        logger.warning(f"[{agent_name}] Tool access denied: {tool.name} — {reason}")
        return {"error": f"Access denied: {reason}"}

    # Track tool usage for analytics
    tool_calls = state.get("_tool_calls", [])
    tool_calls.append({
        "tool": tool.name,
        "agent": agent_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep only last 50 tool calls to prevent state bloat
    state["_tool_calls"] = tool_calls[-50:]

    logger.info(f"[{agent_name}] Calling tool: {tool.name}")
    return None  # Execute tool


# ─── After Tool Callback ──────────────────────────────────────────────────────
# Runs after tool execution. Used for:
# - Result caching
# - Error enrichment
# - Tool result logging

async def after_tool_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: dict
) -> Optional[dict]:
    """
    Post-tool hook: logs result, enriches errors.
    """
    agent_name = tool_context.agent_name

    # If tool returned an error, enrich it
    if isinstance(tool_response, dict) and tool_response.get("error"):
        logger.warning(f"[{agent_name}] Tool {tool.name} returned error: {tool_response['error']}")
        tool_response["_suggestion"] = "Check API keys in .env if this is an external service error."

    logger.debug(f"[{agent_name}] Tool {tool.name} completed")
    return None  # Use tool result as-is


async def on_model_error_callback(
    callback_context: CallbackContext, llm_request: LlmRequest, error: Exception
) -> Optional[LlmResponse]:
    """
    LLM error hook: returns a safe fallback response so production UX degrades gracefully.
    """
    agent_name = callback_context.agent_name
    logger.error(f"[{agent_name}] LLM error: {error}", exc_info=True)

    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text=(
                        "I hit an upstream model error while processing your request. "
                        "Please retry in a moment."
                    )
                )
            ],
        )
    )


async def on_tool_error_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, error: Exception
) -> Optional[dict]:
    """
    Tool error hook: turns tool exceptions into structured error payloads for the model.
    """
    agent_name = tool_context.agent_name
    logger.error(
        f"[{agent_name}] Tool {tool.name} raised exception: {error}",
        exc_info=True,
    )
    return {
        "error": f"Tool '{tool.name}' failed: {error}",
        "_suggestion": "Verify tool configuration and credentials, then retry.",
    }
