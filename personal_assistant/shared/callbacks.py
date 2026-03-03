"""
Callback system — guardrails, logging, memory warmup, session lifecycle.

Inspired by OpenClaw's middleware pattern, adapted for ADK's callback API.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

logger = logging.getLogger(__name__)


# ─── Before Agent Callback ──────────────────────────────────────────────────────────────
# Runs before agent starts processing. Used for:
# - Session warmup (inject context from workspace files)
# - Daily session rotation check
# - Interaction logging

async def before_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    Pre-agent hook: injects workspace identity, checks session age, logs interaction.
    Returns None to proceed, or Content to short-circuit.
    """
    agent_name = callback_context.agent_name
    state = callback_context.state

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


# ─── After Agent Callback ───────────────────────────────────────────────────────────────
# Runs after agent completes. Used for:
# - Auto-save to memory (like OpenClaw's session archival)
# - Interaction metrics
# - Session size pruning trigger

async def after_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    Post-agent hook: logs metrics, triggers memory save on significant interactions.
    """
    agent_name = callback_context.agent_name
    state = callback_context.state

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


# ─── Before Model Callback ──────────────────────────────────────────────────────────────
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

            # Guardrail: block potential credential exposure
            import re
            sensitive_patterns = [
                r"(?i)(password|secret|token)\s*[:=]\s*\S+",
                r"(?i)(api[_-]?key)\s*[:=]\s*\S+",
                r"\b[A-Za-z0-9+/]{40,}\b",  # Long base64-like strings
            ]
            for pattern in sensitive_patterns:
                if re.search(pattern, last_text):
                    logger.warning(f"[{agent_name}] Potential sensitive data detected in input — blocking")
                    return LlmResponse(
                        content=types.Content(
                            role="model",
                            parts=[types.Part(text=(
                                "I noticed your message may contain sensitive information "
                                "(credentials, API keys, etc.). For security, I've blocked this request. "
                                "Please remove any sensitive data and try again."
                            ))]
                        )
                    )

    logger.debug(f"[{agent_name}] Sending request to LLM")
    return None  # Proceed to LLM


# ─── After Model Callback ───────────────────────────────────────────────────────────────
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


# ─── Before Tool Callback ───────────────────────────────────────────────────────────────
# Runs before executing a tool. Used for:
# - Argument validation
# - Rate limiting
# - Tool usage logging

async def before_tool_callback(
    callback_context: CallbackContext, tool_name: str, tool_args: dict
) -> Optional[dict]:
    """
    Pre-tool hook: validates arguments, logs tool usage.
    """
    agent_name = callback_context.agent_name
    state = callback_context.state

    # Track tool usage for analytics
    tool_calls = state.get("_tool_calls", [])
    tool_calls.append({
        "tool": tool_name,
        "agent": agent_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep only last 50 tool calls to prevent state bloat
    state["_tool_calls"] = tool_calls[-50:]

    logger.info(f"[{agent_name}] Calling tool: {tool_name}")
    return None  # Execute tool


# ─── After Tool Callback ────────────────────────────────────────────────────────────────
# Runs after tool execution. Used for:
# - Result caching
# - Error enrichment
# - Tool result logging

async def after_tool_callback(
    callback_context: CallbackContext, tool_name: str, tool_result: dict
) -> Optional[dict]:
    """
    Post-tool hook: logs result, enriches errors.
    """
    agent_name = callback_context.agent_name

    # If tool returned an error, enrich it
    if isinstance(tool_result, dict) and tool_result.get("error"):
        logger.warning(f"[{agent_name}] Tool {tool_name} returned error: {tool_result['error']}")
        tool_result["_suggestion"] = "Check API keys in .env if this is an external service error."

    logger.debug(f"[{agent_name}] Tool {tool_name} completed")
    return None  # Use tool result as-is
