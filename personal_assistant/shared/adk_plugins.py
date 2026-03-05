"""
ADK runtime plugins for run/event lifecycle and error recovery.
"""

import logging
import os
import time
import importlib

from google.adk.plugins import BasePlugin

from .callbacks import (
    on_model_error_callback,
    on_tool_error_callback,
)

logger = logging.getLogger(__name__)


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_external_plugin(path: str) -> BasePlugin | None:
    """
    Load a plugin from import path.

    Supported forms:
      - module.submodule:plugin_symbol
      - module.submodule.plugin_symbol
    """
    candidate = path.strip()
    if not candidate:
        return None

    module_path = ""
    symbol_name = ""
    if ":" in candidate:
        module_path, symbol_name = candidate.split(":", 1)
    else:
        module_path, _, symbol_name = candidate.rpartition(".")
    if not module_path or not symbol_name:
        logger.warning("Invalid plugin path '%s' (expected module:symbol)", candidate)
        return None

    try:
        module = importlib.import_module(module_path)
        symbol = getattr(module, symbol_name)
    except Exception as exc:
        logger.warning("Failed importing plugin '%s': %s", candidate, exc)
        return None

    try:
        if isinstance(symbol, BasePlugin):
            return symbol
        if isinstance(symbol, type) and issubclass(symbol, BasePlugin):
            return symbol()
        if callable(symbol):
            instance = symbol()
            if isinstance(instance, BasePlugin):
                return instance
    except Exception as exc:
        logger.warning("Failed initializing plugin '%s': %s", candidate, exc)
        return None

    logger.warning("Symbol '%s' is not an ADK BasePlugin.", candidate)
    return None


class RuntimeStabilityPlugin(BasePlugin):
    """
    Lightweight plugin that adds:
      - invocation timing
      - event-level observability
      - model/tool error fallback handlers
    """

    def __init__(self):
        super().__init__(name="runtime_stability_plugin")
        self._run_started_at: dict[str, float] = {}

    async def before_run_callback(self, *, invocation_context):
        invocation_id = getattr(invocation_context, "invocation_id", None)
        if invocation_id:
            self._run_started_at[invocation_id] = time.time()
        return None

    async def after_run_callback(self, *, invocation_context):
        invocation_id = getattr(invocation_context, "invocation_id", None)
        if not invocation_id:
            return None
        started = self._run_started_at.pop(invocation_id, None)
        if started is not None:
            duration_ms = int((time.time() - started) * 1000)
            logger.info("Invocation %s completed in %dms", invocation_id, duration_ms)
        return None

    async def on_event_callback(self, *, invocation_context, event):
        # Keep event stream unchanged; this hook is used for runtime observability.
        _ = invocation_context
        _ = event
        return None

    async def on_user_message_callback(self, *, invocation_context, user_message):
        _ = invocation_context
        return user_message

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        return await on_model_error_callback(callback_context, llm_request, error)

    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        return await on_tool_error_callback(tool, tool_args, tool_context, error)


def create_runtime_plugins() -> list[BasePlugin]:
    """
    Build runtime plugin list.

    Always includes RuntimeStabilityPlugin. Built-in ADK plugins can be toggled
    with env vars:
      - ENABLE_DEBUG_LOGGING_PLUGIN=true
      - ENABLE_REFLECT_RETRY_TOOL_PLUGIN=true
    """
    plugins: list[BasePlugin] = [RuntimeStabilityPlugin()]

    if _is_true(os.getenv("ENABLE_DEBUG_LOGGING_PLUGIN")):
        from google.adk.plugins import DebugLoggingPlugin

        plugins.append(DebugLoggingPlugin())

    if _is_true(os.getenv("ENABLE_REFLECT_RETRY_TOOL_PLUGIN")):
        from google.adk.plugins import ReflectAndRetryToolPlugin

        retry_attempts = int(os.getenv("REFLECT_RETRY_MAX_ATTEMPTS", "1"))
        throw_if_exceeded = _is_true(
            os.getenv("REFLECT_RETRY_THROW_IF_EXCEEDED", "false")
        )
        plugins.append(
            ReflectAndRetryToolPlugin(
                max_retries=retry_attempts,
                throw_exception_if_retry_exceeded=throw_if_exceeded,
            )
        )

    extra_plugins = os.getenv("ADK_INTEGRATION_PLUGINS", "").strip()
    if extra_plugins:
        for path in [p.strip() for p in extra_plugins.split(",") if p.strip()]:
            plugin = _load_external_plugin(path)
            if plugin is not None:
                plugins.append(plugin)

    return plugins
