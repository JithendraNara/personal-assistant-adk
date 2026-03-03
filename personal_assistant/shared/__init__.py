"""Shared configuration, prompts, and callbacks."""
from .config import (
    APP_NAME, DEFAULT_MODEL, REASONING_MODEL, USER_PROFILE,
    SOUL_MD, USER_MD, AGENTS_MD, IDENTITY_MD,
    create_session_service, create_memory_service, create_artifact_service,
    validate_config,
)
from .callbacks import (
    before_agent_callback, after_agent_callback,
    before_model_callback, after_model_callback,
    before_tool_callback, after_tool_callback,
)
