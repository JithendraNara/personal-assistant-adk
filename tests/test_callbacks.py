"""Tests for the callback system."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


class MockState(dict):
    """Mock ADK State (mutable dict-like object)."""
    pass


class MockContext:
    """Mock ADK Context for agent callbacks (before_agent, after_agent)."""
    def __init__(self, agent_name="test_agent", state=None):
        self.agent_name = agent_name
        self.state = MockState(state or {})


class MockCallbackContext:
    """Mock ADK CallbackContext for model callbacks (before_model, after_model)."""
    def __init__(self, agent_name="test_agent", state=None):
        self.agent_name = agent_name
        self.state = MockState(state or {})


class MockLlmRequest:
    """Mock LLM request."""
    def __init__(self, text="hello"):
        self.contents = [MagicMock(parts=[MagicMock(text=text)])]


class MockLlmResponse:
    pass


class MockBaseTool:
    """Mock BaseTool for tool callbacks."""
    def __init__(self, name="test_tool"):
        self.name = name


class MockToolContext:
    """Mock ToolContext for tool callbacks."""
    def __init__(self, agent_name="test_agent", state=None):
        self.agent_name = agent_name
        self.state = MockState(state or {})


@pytest.mark.asyncio
async def test_before_agent_loads_identity():
    from personal_assistant.shared.callbacks import before_agent_callback
    ctx = MockContext(state={})
    result = await before_agent_callback(ctx)
    assert result is None  # Should proceed
    assert ctx.state.get("_identity_loaded") is True
    assert ctx.state.get("_interaction_count") == 1


@pytest.mark.asyncio
async def test_before_agent_increments_count():
    from personal_assistant.shared.callbacks import before_agent_callback
    ctx = MockContext(state={"_interaction_count": 5, "_identity_loaded": True})
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
    ctx = MockContext(
        agent_name="research_agent",
        state={"temp:turn_start_time": time.time(), "_interaction_count": 1}
    )
    result = await after_agent_callback(ctx)
    assert result is None
    assert "research_agent" in ctx.state.get("user:agents_used", [])


@pytest.mark.asyncio
async def test_before_tool_logs_usage():
    from personal_assistant.shared.callbacks import before_tool_callback
    tool = MockBaseTool(name="web_search")
    tool_ctx = MockToolContext(agent_name="research_agent")
    result = await before_tool_callback(tool, {"query": "test"}, tool_ctx)
    assert result is None  # Should proceed
    assert len(tool_ctx.state.get("_tool_calls", [])) == 1
    assert tool_ctx.state["_tool_calls"][0]["tool"] == "web_search"


@pytest.mark.asyncio
async def test_after_tool_enriches_errors():
    from personal_assistant.shared.callbacks import after_tool_callback
    tool = MockBaseTool(name="web_search")
    tool_ctx = MockToolContext(agent_name="research_agent")
    error_result = {"error": "API rate limit exceeded"}
    result = await after_tool_callback(tool, {}, tool_ctx, error_result)
    assert result is None  # Should use result as-is
    assert "_suggestion" in error_result  # Error should be enriched
