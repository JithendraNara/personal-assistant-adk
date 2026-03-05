"""Tests for shared configuration."""
from personal_assistant.shared.config import (
    APP_NAME, USER_PROFILE, SOUL_MD, USER_MD,
    create_session_service, create_artifact_service, create_default_run_config, create_adk_app,
    validate_config, _load_workspace_file,
)


def test_app_name():
    assert APP_NAME == "personal_assistant"


def test_user_profile_structure():
    assert "name" in USER_PROFILE
    assert "roles" in USER_PROFILE
    assert "locations" in USER_PROFILE
    assert USER_PROFILE["name"] == "Jithendra"
    assert "Data Analyst" in USER_PROFILE["roles"]


def test_workspace_files_loaded():
    """Workspace markdown files should be loaded at import time."""
    assert isinstance(SOUL_MD, str)
    assert isinstance(USER_MD, str)
    # Should have content if workspace/ files exist
    if SOUL_MD:
        assert "Persona" in SOUL_MD or "Soul" in SOUL_MD


def test_load_nonexistent_workspace_file():
    result = _load_workspace_file("NONEXISTENT.md")
    assert result == ""


def test_validate_config_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "gemini-2.0-flash")
    result = validate_config()
    assert len(result["errors"]) > 0
    assert "GOOGLE_API_KEY" in result["errors"][-1]


def test_validate_config_with_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "gemini-2.0-flash")
    result = validate_config()
    assert len(result["errors"]) == 0


def test_validate_config_production_requires_app_api_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("APP_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    result = validate_config()
    assert any("APP_API_KEY" in err for err in result["errors"])


def test_validate_config_production_with_app_api_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("APP_API_KEY", "prod-token")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    result = validate_config()
    assert not any("APP_API_KEY" in err for err in result["errors"])


def test_minimax_anthropic_warns_without_base_url(monkeypatch):
    monkeypatch.setenv("DEFAULT_MODEL", "anthropic/MiniMax-M2.5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    result = validate_config()
    assert any("ANTHROPIC_BASE_URL" in warning for warning in result["warnings"])


def test_create_session_service_respects_runtime_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SESSION_DB_URL", "sqlite:///sessions.db")
    service = create_session_service()
    assert type(service).__name__ == "InMemorySessionService"

    monkeypatch.setenv("SESSION_DB_URL", "sqlite:///test_sessions.db")
    service = create_session_service()
    assert type(service).__name__ == "DatabaseSessionService"


def test_create_artifact_service_defaults_in_memory(monkeypatch):
    monkeypatch.setenv("ARTIFACT_SERVICE", "in_memory")
    monkeypatch.delenv("ARTIFACT_GCS_BUCKET", raising=False)
    monkeypatch.delenv("ARTIFACT_FILE_DIR", raising=False)
    service = create_artifact_service()
    assert type(service).__name__ == "InMemoryArtifactService"


def test_create_artifact_service_file_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("ARTIFACT_SERVICE", "file")
    monkeypatch.setenv("ARTIFACT_FILE_DIR", str(tmp_path / "artifacts"))
    monkeypatch.delenv("ARTIFACT_GCS_BUCKET", raising=False)
    service = create_artifact_service()
    assert type(service).__name__ == "FileArtifactService"


def test_create_default_run_config_none(monkeypatch):
    monkeypatch.setenv("ADK_SAVE_INPUT_BLOBS", "false")
    monkeypatch.setenv("ADK_DEFAULT_STREAMING_MODE", "none")
    monkeypatch.setenv("ADK_MAX_LLM_CALLS", "500")
    cfg = create_default_run_config()
    assert cfg is None


def test_create_default_run_config_with_overrides(monkeypatch):
    monkeypatch.setenv("ADK_SAVE_INPUT_BLOBS", "true")
    cfg = create_default_run_config()
    assert cfg is not None
    assert cfg.model_dump().get("save_input_blobs_as_artifacts") is True


def test_create_adk_app_includes_plugins(monkeypatch):
    monkeypatch.setenv("ADK_ENABLE_RESUMABILITY", "true")
    from personal_assistant.agent import root_agent

    app = create_adk_app(root_agent)
    assert app is not None
    assert app.name == APP_NAME
    assert len(app.plugins) >= 1
