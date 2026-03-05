"""
ADK Evaluation Tests — routing accuracy and response quality.

Tests that verify agents handle queries correctly:
  1. Routing: root_agent delegates to the right specialist
  2. Response quality: responses are relevant and well-formatted
  3. Tool usage: correct tools are called for queries
  4. Security: tool access policies are enforced

Run:
    pytest tests/test_eval.py -v
"""

from personal_assistant.shared.security import check_tool_access, sanitize_input


# ─── Routing Accuracy Tests ──────────────────────────────────────────────────

class TestToolAccessPolicies:
    """Test that per-agent tool access policies are correctly enforced."""

    def test_research_agent_allowed_tools(self):
        """Research agent should access web tools."""
        allowed, _ = check_tool_access("research_agent", "web_search")
        assert allowed
        allowed, _ = check_tool_access("research_agent", "fetch_webpage_summary")
        assert allowed
        allowed, _ = check_tool_access("research_agent", "get_news_headlines")
        assert allowed

    def test_research_agent_denied_tools(self):
        """Research agent should NOT access non-web tools."""
        allowed, _ = check_tool_access("research_agent", "analyze_code")
        assert not allowed
        allowed, _ = check_tool_access("research_agent", "get_stock_quote")
        assert not allowed
        allowed, _ = check_tool_access("research_agent", "create_task")
        assert not allowed

    def test_scheduler_agent_allowed_tools(self):
        """Scheduler agent should access scheduling tools."""
        for tool in ["create_task", "list_tasks", "update_task_status",
                      "build_daily_plan", "set_reminder"]:
            allowed, _ = check_tool_access("scheduler_agent", tool)
            assert allowed, f"scheduler_agent should access {tool}"

    def test_scheduler_agent_denied_tools(self):
        """Scheduler agent should NOT access non-scheduling tools."""
        allowed, _ = check_tool_access("scheduler_agent", "web_search")
        assert not allowed
        allowed, _ = check_tool_access("scheduler_agent", "get_stock_quote")
        assert not allowed

    def test_finance_agent_policies(self):
        """Finance agent has deny list, not allow list."""
        # Should be denied tech tools
        allowed, _ = check_tool_access("finance_agent", "analyze_code")
        assert not allowed
        allowed, _ = check_tool_access("finance_agent", "compare_technologies")
        assert not allowed
        # Should be allowed everything else (no allow list = open access minus denies)
        allowed, _ = check_tool_access("finance_agent", "get_stock_quote")
        assert allowed

    def test_root_agent_full_access(self):
        """root_agent should have full access (no policy = allow all)."""
        for tool in ["web_search", "create_task", "get_stock_quote",
                      "analyze_code", "get_nfl_scores"]:
            allowed, _ = check_tool_access("root_agent", tool)
            assert allowed, f"root_agent should access {tool}"

    def test_unknown_agent_full_access(self):
        """Unknown agents (no policy defined) get full access."""
        allowed, _ = check_tool_access("unknown_agent_xyz", "web_search")
        assert allowed

    def test_sports_agent_policies(self):
        """Sports agent should only access sports tools."""
        allowed, _ = check_tool_access("sports_agent", "get_nfl_scores")
        assert allowed
        allowed, _ = check_tool_access("sports_agent", "web_search")
        assert not allowed

    def test_workflow_agent_policies(self):
        """Workflow sub-agents should be restricted to their intended tools."""
        allowed, _ = check_tool_access("parallel_weather", "get_current_weather")
        assert allowed
        allowed, _ = check_tool_access("parallel_weather", "web_search")
        assert not allowed

        allowed, _ = check_tool_access("parallel_finance", "get_stock_quote")
        assert allowed
        allowed, _ = check_tool_access("parallel_finance", "calculate_budget")
        assert not allowed


# ─── Input Sanitization Tests ────────────────────────────────────────────────

class TestInputSanitization:
    """Test that sensitive data patterns are correctly detected and redacted."""

    def test_ssn_detection(self):
        """Should detect Social Security Numbers."""
        _, detected = sanitize_input("My SSN is 123-45-6789")
        assert "SSN" in detected

    def test_password_detection(self):
        """Should detect password patterns."""
        _, detected = sanitize_input("password=my_secret_pass123")
        assert "password" in detected

    def test_clean_input_passes(self):
        """Normal text should not trigger any detections."""
        _, detected = sanitize_input("What's the weather like today?")
        assert len(detected) == 0

    def test_credit_card_detection(self):
        """Should detect 16-digit card numbers."""
        _, detected = sanitize_input("Card: 4111111111111111")
        assert "credit_card" in detected

    def test_redaction_preserves_structure(self):
        """Redacted text should have [REDACTED:type] markers."""
        sanitized, _ = sanitize_input("My SSN is 123-45-6789 and that's all")
        assert "[REDACTED:SSN]" in sanitized
        assert "123-45-6789" not in sanitized


# ─── Skills System Tests ─────────────────────────────────────────────────────

class TestSkillsSystem:
    """Test skill discovery and context generation."""

    def test_discover_skills(self):
        """Should discover skills from workspace/skills/ directory."""
        from personal_assistant.shared.skills import discover_skills
        skills = discover_skills()
        assert len(skills) >= 3  # web-research, interview-prep, daily-standup

    def test_skill_parsing(self):
        """Each skill should have name, description, and routing info."""
        from personal_assistant.shared.skills import discover_skills
        skills = discover_skills()
        for skill in skills:
            assert skill.name, f"Skill missing name: {skill}"
            assert skill.description, f"Skill missing description: {skill.name}"
            assert skill.agent_target, f"Skill missing agent target: {skill.name}"

    def test_skill_context_generation(self):
        """get_skill_context should return relevant context for targeted agents."""
        from personal_assistant.shared.skills import discover_skills, get_skill_context
        skills = discover_skills()

        # research_agent should get web-research skill context
        ctx = get_skill_context(skills, "research_agent")
        assert "web-research" in ctx.lower() or "research" in ctx.lower()

        # scheduler_agent should get daily-standup skill context
        ctx = get_skill_context(skills, "scheduler_agent")
        assert len(ctx) > 0

    def test_skill_when_to_use(self):
        """Skills should have When to Use triggers parsed."""
        from personal_assistant.shared.skills import discover_skills
        skills = discover_skills()
        research = next((s for s in skills if s.name == "web-research"), None)
        assert research is not None
        assert len(research.when_to_use) > 0

    def test_build_skill_toolset_native_adk(self):
        """Skill toolset builder should produce ADK SkillToolset for targeted agents."""
        from personal_assistant.shared.skills import build_skill_toolsets
        toolsets = build_skill_toolsets("research_agent")
        assert len(toolsets) >= 1
        assert type(toolsets[0]).__name__ == "SkillToolset"


# ─── A2A Agent Card Tests ────────────────────────────────────────────────────

class TestA2AAgentCard:
    """Test A2A Agent Card generation."""

    def test_agent_card_structure(self):
        """Agent card should have required A2A fields."""
        from personal_assistant.shared.a2a import build_agent_card
        card = build_agent_card()
        assert card["name"] == "Personal Assistant"
        assert card["protocolVersion"] == "0.3"
        assert "url" in card
        assert "skills" in card
        assert "capabilities" in card

    def test_agent_card_skills(self):
        """Agent card should define skills for all specialist agents."""
        from personal_assistant.shared.a2a import build_agent_card
        card = build_agent_card()
        skills = card["skills"]
        assert len(skills) >= 7  # One per specialist agent
        skill_ids = {s["id"] for s in skills}
        assert "research" in skill_ids
        assert "scheduling" in skill_ids
        assert "finance" in skill_ids

    def test_agent_card_custom_url(self):
        """Agent card should accept custom base URL."""
        from personal_assistant.shared.a2a import build_agent_card
        card = build_agent_card(base_url="https://my-agent.example.com")
        assert "https://my-agent.example.com" in card["url"]


# ─── Plugin System Tests ─────────────────────────────────────────────────────

class TestPluginSystem:
    """Test plugin discovery and lifecycle."""

    def test_plugin_manager_init(self):
        """PluginManager should initialize without errors."""
        from personal_assistant.shared.plugins import PluginManager
        pm = PluginManager(plugins_dir="nonexistent")
        plugins = pm.discover()
        assert len(plugins) == 0

    def test_plugin_list_empty(self):
        """Empty plugins dir should return empty list."""
        from personal_assistant.shared.plugins import PluginManager
        pm = PluginManager(plugins_dir="nonexistent")
        assert pm.list_plugins() == []
