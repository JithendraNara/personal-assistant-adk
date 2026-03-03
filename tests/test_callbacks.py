"""Tests for the callback system."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class MockCallbackContext:
    """Mock ADK CallbackContext for testing."""
    def __init__(self, agent_name="test_agent", state=None):
        self.agent_name = agent_name
        self.state = state or {}


class MockLlmRequest:
    """Mock LLM request."""
    def __init__(self, text="hello"):
        self.contents = [MagicMock(parts=[MagicMock(text=text)])]


class MockLlmResponse:
    pass


@pytest.mark.asyncio
async def test_before_agent_loads_identity():
    from personal_assistant.shared.callbacks import before_agent_callback
    ctx = MockCallbackContext(state={})
    result = await before_agent_callback(ctx)
    assert result is None  # Should proceed
    assert ctx.state.get("_identity_loaded") is True
    assert ctx.state.get("_interaction_count") == 1


@pytest.mark.asyncio
async def test_before_agent_increments_count():
    from personal_assistant.shared.callbacks import before_agent_callback
    ctx = MockCallbackContext(state={"_interaction_count": 5, "_identity_loaded": True})
    await before_agent_callback(ctx)
    assert ctx.state["_interaction_count"] == 6


@pytest.mark.asyncio
async def test_before_model_blocks_credentials():
    from personal_assistant.shared.callbacks import before_model_callback
    ctx = MockCallbackContext()
    request = MockLlmRequest(text="My password: secretpass123")
    result = await before_model_callback(ctx, request)
    assert result is not None  # Should block
    assert "sensitive" in result.content.parts[0].text.lower()


@pytest.mark.asyncio
async def test_before_model_allows_normal_text():
    from personal_assistant.shared.callbacks import before_model_callback
    ctx = MockCallbackContext()
    request = MockLlmRequest(text="What's the weather today?")
    result = await before_model_callback(ctx, request)
    assert result is None  # Should proceed


@pytest.mark.asyncio
async def test_after_agent_tracks_agents_used():
    from personal_assistant.shared.callbacks import after_agent_callback
    import time
    ctx = MockCallbackContext(
        agent_name="research_agent",
        state={"temp:turn_start_time": time.time(), "_interaction_count": 1}
    )
    result = await after_agent_callback(ctx)
    assert result is None
    assert "research_agent" in ctx.state.get("user:agents_used", [])
