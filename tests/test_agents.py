"""Tests for agent structure and configuration."""


def test_root_agent_exists():
    from personal_assistant.agent import root_agent
    assert root_agent is not None
    assert root_agent.name == "personal_assistant"


def test_root_agent_has_sub_agents():
    from personal_assistant.agent import root_agent
    sub_names = [a.name for a in root_agent.sub_agents]
    assert "research_agent" in sub_names
    assert "data_agent" in sub_names
    assert "career_agent" in sub_names
    assert "finance_agent" in sub_names
    assert "sports_agent" in sub_names
    assert "scheduler_agent" in sub_names
    assert "tech_agent" in sub_names
    assert "daily_briefing" in sub_names
    assert "info_gatherer" in sub_names


def test_root_agent_has_callbacks():
    from personal_assistant.agent import root_agent
    assert root_agent.before_agent_callback is not None
    assert root_agent.after_agent_callback is not None
    assert root_agent.before_model_callback is not None
    assert root_agent.after_model_callback is not None
    assert root_agent.on_model_error_callback is not None
    assert root_agent.before_tool_callback is not None
    assert root_agent.after_tool_callback is not None
    assert root_agent.on_tool_error_callback is not None


def test_root_agent_uses_instruction_provider():
    from personal_assistant.agent import root_agent
    # instruction should be a callable, not a static string
    assert callable(root_agent.instruction)


def test_specialist_agents_have_output_keys():
    from personal_assistant.agents import (
        career_agent,
        data_agent,
        finance_agent,
        research_agent,
        scheduler_agent,
        sports_agent,
        tech_agent,
    )
    assert research_agent.output_key == "research_last_topic"
    assert data_agent.output_key == "data_last_analysis"
    assert career_agent.output_key == "career_last_search"
    assert finance_agent.output_key == "finance_last_check"
    assert sports_agent.output_key == "sports_last_update"
    assert scheduler_agent.output_key == "scheduler_last_tasks"
    assert tech_agent.output_key == "tech_last_query"


def test_daily_briefing_is_sequential():
    from google.adk.agents import SequentialAgent

    from personal_assistant.agent import daily_briefing
    assert isinstance(daily_briefing, SequentialAgent)
    sub_names = [a.name for a in daily_briefing.sub_agents]
    assert "briefing_weather" in sub_names
    assert "briefing_tasks" in sub_names
    assert "briefing_news" in sub_names
    assert "briefing_composer" in sub_names


def test_info_gatherer_is_parallel():
    from google.adk.agents import ParallelAgent

    from personal_assistant.agent import info_gatherer
    assert isinstance(info_gatherer, ParallelAgent)


def test_workflow_subagents_have_runtime_tools():
    from personal_assistant.agent import (
        briefing_news,
        briefing_weather,
        parallel_finance,
        parallel_sports,
        parallel_weather,
    )

    def fn_names(agent):
        return {getattr(tool, "__name__", "") for tool in (agent.tools or [])}

    assert "get_current_weather" in fn_names(briefing_weather)
    assert "get_news_headlines" in fn_names(briefing_news)
    assert "get_current_weather" in fn_names(parallel_weather)
    assert "get_nfl_scores" in fn_names(parallel_sports)
    assert "get_cricket_scores" in fn_names(parallel_sports)
    assert "get_f1_standings" in fn_names(parallel_sports)
    assert "get_stock_quote" in fn_names(parallel_finance)
