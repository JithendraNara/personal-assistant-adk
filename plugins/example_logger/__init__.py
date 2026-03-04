"""
Example Logger Plugin — logs all agent turns.

Demonstrates the plugin hook system.
Hooks implemented: on_load, on_unload, before_turn, after_turn
"""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("plugin.example_logger")

_config = {}
_log_file = None


def on_load(config: dict):
    """Called when plugin is loaded."""
    global _config, _log_file
    _config = config
    _log_file = config.get("log_file", "data/plugin_logs.jsonl")
    logger.info(f"Example logger plugin loaded, writing to {_log_file}")


def on_unload():
    """Called when plugin is unloaded."""
    logger.info("Example logger plugin unloaded")


def before_turn(agent_name: str, message: str, **kwargs):
    """Called before each agent turn."""
    entry = {
        "event": "before_turn",
        "agent": agent_name,
        "message_length": len(message),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _write_log(entry)
    if _config.get("verbose"):
        logger.info(f"[Logger] Before turn: {agent_name} ({len(message)} chars)")


def after_turn(agent_name: str, response: str, duration_ms: int = 0, **kwargs):
    """Called after each agent turn."""
    entry = {
        "event": "after_turn",
        "agent": agent_name,
        "response_length": len(response),
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _write_log(entry)
    if _config.get("verbose"):
        logger.info(f"[Logger] After turn: {agent_name} ({duration_ms}ms, {len(response)} chars)")


def _write_log(entry: dict):
    """Append a log entry to the JSONL file."""
    try:
        import os
        os.makedirs(os.path.dirname(_log_file), exist_ok=True)
        with open(_log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write plugin log: {e}")
