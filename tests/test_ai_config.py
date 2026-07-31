"""Tests for AI Chat configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import create_config, resolve_config_name, DEV_SECRET_KEY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAFE_FAKE_KEY = "placeholder-change-in-env"
SAFE_FAKE_BASE = "https://api.example.com/v1"
SAFE_FAKE_MODEL = "example-model"
FAKE_SECRET_KEY = "test-secret-not-for-production"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests never read real .env or leak real credentials.

    All AI-related env vars are unpatch via monkeypatch so the test
    environment stays clean.  A single non‑secret env is left to
    prevent Flask app factory log warnings but the test assertions
    do NOT depend on it.
    """
    for key in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_API_BASE",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "DEEPSEEK_MAX_OUTPUT_TOKENS",
        "DEEPSEEK_THINKING",
        "DEEPSEEK_TRUST_ENV",
        "DEEPSEEK_REASONING_EFFORT",
        "AI_MAX_TOOL_ROUNDS",
        "AI_MAX_HISTORY_MESSAGES",
        "AI_MAX_MESSAGE_LENGTH",
        "AI_CONFIRMATION_TOKEN_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("SECRET_KEY", FAKE_SECRET_KEY)
    # Prevent accidental .env load from the real project
    monkeypatch.setenv("APP_ENV", "testing")


def _build_config_from_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> dict:
    """Set env vars, create config, return the final mapping."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    config_obj = create_config("testing")
    mapping = config_obj.to_mapping()
    # finalize normally needs project / instance paths; skip for mapping tests
    return mapping


def _ai_config_state(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> dict:
    """Return the AI‑specific sub‑dictionary of the config mapping."""
    mapping = _build_config_from_env(monkeypatch, env)
    return {
        k: mapping[k]
        for k in (
            "DEEPSEEK_API_KEY",
            "DEEPSEEK_API_BASE",
            "DEEPSEEK_MODEL",
            "DEEPSEEK_TIMEOUT_SECONDS",
            "DEEPSEEK_MAX_OUTPUT_TOKENS",
            "DEEPSEEK_THINKING",
            "DEEPSEEK_TRUST_ENV",
            "DEEPSEEK_REASONING_EFFORT",
            "AI_MAX_TOOL_ROUNDS",
            "AI_MAX_HISTORY_MESSAGES",
            "AI_MAX_MESSAGE_LENGTH",
            "AI_CONFIRMATION_TOKEN_TTL_SECONDS",
        )
        if k in mapping
    }


# ---------------------------------------------------------------------------
# 1.  All AI env vars present → values read correctly
# ---------------------------------------------------------------------------


def test_all_ai_env_vars_read_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    ai_env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TIMEOUT_SECONDS": "30",
        "DEEPSEEK_MAX_OUTPUT_TOKENS": "4096",
        "DEEPSEEK_THINKING": "true",
        "DEEPSEEK_REASONING_EFFORT": "high",
        "AI_MAX_TOOL_ROUNDS": "10",
        "AI_MAX_HISTORY_MESSAGES": "20",
        "AI_MAX_MESSAGE_LENGTH": "4000",
        "AI_CONFIRMATION_TOKEN_TTL_SECONDS": "120",
    }
    cfg = _ai_config_state(monkeypatch, ai_env)

    assert cfg["DEEPSEEK_API_KEY"] == SAFE_FAKE_KEY
    assert cfg["DEEPSEEK_API_BASE"] == SAFE_FAKE_BASE
    assert cfg["DEEPSEEK_MODEL"] == SAFE_FAKE_MODEL
    assert cfg["DEEPSEEK_TIMEOUT_SECONDS"] == 30
    assert cfg["DEEPSEEK_MAX_OUTPUT_TOKENS"] == 4096
    assert cfg["DEEPSEEK_THINKING"] is True
    assert cfg["DEEPSEEK_REASONING_EFFORT"] == "high"
    assert cfg["AI_MAX_TOOL_ROUNDS"] == 10
    assert cfg["AI_MAX_HISTORY_MESSAGES"] == 20
    assert cfg["AI_MAX_MESSAGE_LENGTH"] == 4000
    assert cfg["AI_CONFIRMATION_TOKEN_TTL_SECONDS"] == 120


# ---------------------------------------------------------------------------
# 2-4.  Missing DeepSeek required config → app still creates, AI is not configured
# ---------------------------------------------------------------------------


def test_missing_api_key_app_still_creates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing DEEPSEEK_API_KEY → AI Chat reports not configured."""
    env = {
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg.get("DEEPSEEK_API_KEY") is None or cfg["DEEPSEEK_API_KEY"] == ""


def test_missing_api_base_app_still_creates(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg.get("DEEPSEEK_API_BASE") is None or cfg["DEEPSEEK_API_BASE"] == ""


def test_missing_model_app_still_creates(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg.get("DEEPSEEK_MODEL") is None or cfg["DEEPSEEK_MODEL"] == ""


# ---------------------------------------------------------------------------
# 5.  AI Chat not configured when required DeepSeek vars are missing
# ---------------------------------------------------------------------------


def test_ai_not_configured_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config includes an ai_configured boolean that is False when any
    required DeepSeek variable is missing."""
    env = {
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _build_config_from_env(monkeypatch, env)
    assert cfg.get("AI_CONFIGURED") is False


def test_ai_configured_when_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _build_config_from_env(monkeypatch, env)
    assert cfg.get("AI_CONFIGURED") is True


# ---------------------------------------------------------------------------
# 6-7.  No hardcoded API Base or Model fallback
# ---------------------------------------------------------------------------


def test_no_hardcoded_api_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """When DEEPSEEK_API_BASE is not set, the config value must be empty / None,
    not a hardcoded default like 'https://api.deepseek.com'."""
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _ai_config_state(monkeypatch, env)
    value = cfg.get("DEEPSEEK_API_BASE")
    assert not value, f"Should not have a hardcoded fallback, got: {value!r}"


def test_no_hardcoded_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """When DEEPSEEK_MODEL is not set, the config value must be empty / None,
    not a hardcoded default like 'deepseek-chat'."""
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
    }
    cfg = _ai_config_state(monkeypatch, env)
    value = cfg.get("DEEPSEEK_MODEL")
    assert not value, f"Should not have a hardcoded fallback, got: {value!r}"


# ---------------------------------------------------------------------------
# 8.  Numeric config values are parsed to the correct type
# ---------------------------------------------------------------------------


def test_numeric_config_parsed_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TIMEOUT_SECONDS": "60",
        "DEEPSEEK_MAX_OUTPUT_TOKENS": "8192",
        "AI_MAX_TOOL_ROUNDS": "5",
        "AI_MAX_HISTORY_MESSAGES": "50",
        "AI_MAX_MESSAGE_LENGTH": "10000",
        "AI_CONFIRMATION_TOKEN_TTL_SECONDS": "300",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_TIMEOUT_SECONDS"] == 60
    assert cfg["DEEPSEEK_MAX_OUTPUT_TOKENS"] == 8192
    assert cfg["AI_MAX_TOOL_ROUNDS"] == 5
    assert cfg["AI_MAX_HISTORY_MESSAGES"] == 50
    assert cfg["AI_MAX_MESSAGE_LENGTH"] == 10000
    assert cfg["AI_CONFIRMATION_TOKEN_TTL_SECONDS"] == 300


def test_invalid_numeric_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid numeric env var values result in None, not a crash."""
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TIMEOUT_SECONDS": "not-a-number",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg.get("DEEPSEEK_TIMEOUT_SECONDS") is None


# ---------------------------------------------------------------------------
# 9.  Thinking enabled / disabled
# ---------------------------------------------------------------------------


def test_thinking_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_THINKING": "true",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_THINKING"] is True


def test_thinking_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_THINKING": "false",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_THINKING"] is False


def test_thinking_unset_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_THINKING"] is False


# ---------------------------------------------------------------------------
# 10.  DEEPSEEK_TRUST_ENV boolean parsing
# ---------------------------------------------------------------------------


def test_trust_env_false(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TRUST_ENV": "false",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_TRUST_ENV"] is False


def test_trust_env_true(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TRUST_ENV": "true",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_TRUST_ENV"] is True


@pytest.mark.parametrize("raw,expected", [
    ("true", True),
    ("TRUE", True),
    ("True", True),
    ("1", True),
    ("yes", True),
    ("YES", True),
    ("on", True),
    ("ON", True),
    ("false", False),
    ("FALSE", False),
    ("False", False),
    ("0", False),
    ("no", False),
    ("off", False),
    ("", False),
])
def test_trust_env_various_boolean_forms(monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TRUST_ENV": raw,
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_TRUST_ENV"] is expected, f"DEEPSEEK_TRUST_ENV={raw!r} should be {expected}"


def test_trust_env_invalid_value_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid (non-boolean) values produce False as the controlled result."""
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
        "DEEPSEEK_TRUST_ENV": "garbage",
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_TRUST_ENV"] is False


def test_trust_env_unset_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DEEPSEEK_API_KEY": SAFE_FAKE_KEY,
        "DEEPSEEK_API_BASE": SAFE_FAKE_BASE,
        "DEEPSEEK_MODEL": SAFE_FAKE_MODEL,
    }
    cfg = _ai_config_state(monkeypatch, env)
    assert cfg["DEEPSEEK_TRUST_ENV"] is False


# ---------------------------------------------------------------------------
# 11.  SECRET_KEY and DEEPSEEK_API_KEY are independent
# ---------------------------------------------------------------------------


def test_secret_key_and_deepseek_key_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting SECRET_KEY must not change DEEPSEEK_API_KEY and vice‑versa."""
    monkeypatch.setenv("SECRET_KEY", "independent-secret")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "independent-api-key")
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)

    cfg = _build_config_from_env(monkeypatch, {})
    assert cfg["SECRET_KEY"] == "independent-secret"
    assert cfg["DEEPSEEK_API_KEY"] == "independent-api-key"
    assert cfg["SECRET_KEY"] != cfg["DEEPSEEK_API_KEY"]


# ---------------------------------------------------------------------------
# 11.  Unsafe SECRET_KEY → write confirmation marked unavailable
# ---------------------------------------------------------------------------


def test_dev_secret_key_marks_write_confirmation_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SECRET_KEY is the development default, AI_WRITE_CONFIRMATION
    should be False."""
    monkeypatch.setenv("SECRET_KEY", DEV_SECRET_KEY)
    monkeypatch.setenv("DEEPSEEK_API_KEY", SAFE_FAKE_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)

    cfg = _build_config_from_env(monkeypatch, {})
    assert cfg.get("AI_WRITE_CONFIRMATION") is False


def test_secure_secret_key_marks_write_confirmation_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", FAKE_SECRET_KEY)
    monkeypatch.setenv("DEEPSEEK_API_KEY", SAFE_FAKE_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)

    cfg = _build_config_from_env(monkeypatch, {})
    assert cfg.get("AI_WRITE_CONFIRMATION") is True


def test_missing_secret_key_marks_write_confirmation_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", SAFE_FAKE_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)

    cfg = _build_config_from_env(monkeypatch, {})
    assert cfg.get("AI_WRITE_CONFIRMATION") is False


# ---------------------------------------------------------------------------
# 15.  reasoning_effort validation
# ---------------------------------------------------------------------------


def _reasoning_config(
    monkeypatch: pytest.MonkeyPatch,
    effort: str | None,
    thinking: bool = True,
) -> dict:
    """Build config with specified reasoning_effort and thinking."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", SAFE_FAKE_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)
    monkeypatch.setenv("DEEPSEEK_THINKING", "true" if thinking else "false")
    if effort is not None:
        monkeypatch.setenv("DEEPSEEK_REASONING_EFFORT", effort)
    else:
        monkeypatch.delenv("DEEPSEEK_REASONING_EFFORT", raising=False)
    return _build_config_from_env(monkeypatch, {})


def test_reasoning_high_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _reasoning_config(monkeypatch, "high")
    assert cfg["AI_CONFIGURED"] is True


def test_reasoning_max_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _reasoning_config(monkeypatch, "max")
    assert cfg["AI_CONFIGURED"] is True


def test_reasoning_medium_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _reasoning_config(monkeypatch, "medium")
    assert cfg["AI_CONFIGURED"] is False


def test_reasoning_low_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _reasoning_config(monkeypatch, "low")
    assert cfg["AI_CONFIGURED"] is False


def test_reasoning_arbitrary_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _reasoning_config(monkeypatch, "arbitrary")
    assert cfg["AI_CONFIGURED"] is False


def test_reasoning_missing_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _reasoning_config(monkeypatch, None)
    assert cfg["AI_CONFIGURED"] is False


def test_reasoning_illegal_ignored_when_thinking_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When thinking is disabled, invalid reasoning_effort must not affect configuration."""
    cfg = _reasoning_config(monkeypatch, "medium", thinking=False)
    assert cfg["AI_CONFIGURED"] is True
    assert cfg["DEEPSEEK_THINKING"] is False


# ---------------------------------------------------------------------------
# 12.  Flask app creates even when AI config is missing
# ---------------------------------------------------------------------------


def test_flask_app_creates_without_ai_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Flask app factory must succeed even when no DeepSeek config exists."""
    from app import create_app

    app = create_app(config_name="testing", load_env=False)
    assert app is not None
    # The app should have our expected AI keys (with empty / None values)
    assert "DEEPSEEK_API_KEY" in app.config or "DEEPSEEK_API_BASE" in app.config


# ---------------------------------------------------------------------------
# 13.  HTML response does not contain test credentials
# ---------------------------------------------------------------------------


def test_html_does_not_leak_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rendering the dashboard page must not include API key or secret in the
    HTML output."""
    from app import create_app

    monkeypatch.setenv("DEEPSEEK_API_KEY", SAFE_FAKE_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)

    app = create_app(config_name="testing", load_env=False)
    client = app.test_client()
    user_service = app.extensions["user_service_factory"]()
    user = user_service.get_user_by_username("html-admin") or user_service.create_user("html-admin", "secret1", "admin")
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["auth_version"] = user["auth_version"]
        session["csrf_token"] = "test-csrf-token"

    for path in ("/", "/students"):
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert SAFE_FAKE_KEY not in html, "API Key leaked into HTML"
        assert FAKE_SECRET_KEY not in html, "SECRET_KEY leaked into HTML"


# ---------------------------------------------------------------------------
# 14.  Flask app creates successfully with all AI config present
# ---------------------------------------------------------------------------


def test_flask_app_creates_with_all_ai_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import create_app

    monkeypatch.setenv("DEEPSEEK_API_KEY", SAFE_FAKE_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", SAFE_FAKE_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", SAFE_FAKE_MODEL)
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "4096")
    monkeypatch.setenv("DEEPSEEK_THINKING", "true")
    monkeypatch.setenv("DEEPSEEK_REASONING_EFFORT", "high")
    monkeypatch.setenv("AI_MAX_TOOL_ROUNDS", "10")
    monkeypatch.setenv("AI_MAX_HISTORY_MESSAGES", "20")
    monkeypatch.setenv("AI_MAX_MESSAGE_LENGTH", "4000")
    monkeypatch.setenv("AI_CONFIRMATION_TOKEN_TTL_SECONDS", "120")

    app = create_app(config_name="testing", load_env=False)
    assert app is not None
    assert app.config.get("AI_CONFIGURED") is True


def test_placeholder_secret_key_disables_write_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SECRET_KEY",
        "replace-with-development-secret",
    )

    config_obj = create_config("testing")
    mapping = config_obj.to_mapping()

    assert mapping["AI_WRITE_CONFIRMATION"] is False
