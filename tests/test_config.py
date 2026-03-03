"""Tests for shared configuration."""
import pytest
from personal_assistant.shared.config import (
    APP_NAME, USER_PROFILE, SOUL_MD, USER_MD,
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
    monkeypatch.setattr("personal_assistant.shared.config.GOOGLE_API_KEY", "")
    result = validate_config()
    assert len(result["errors"]) > 0
    assert "GOOGLE_API_KEY" in result["errors"][0]


def test_validate_config_with_api_key(monkeypatch):
    monkeypatch.setattr("personal_assistant.shared.config.GOOGLE_API_KEY", "test-key")
    result = validate_config()
    assert len(result["errors"]) == 0
