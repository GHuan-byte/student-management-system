"""Tests for DeepSeekClient — basic text completion slice."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.config import create_config

# ---------------------------------------------------------------------------
# Safe test values (never real credentials)
# ---------------------------------------------------------------------------

TEST_API_KEY = "test-api-key-not-secret"
TEST_API_BASE = "https://api.example.invalid"
TEST_MODEL = "example-model"
TEST_MESSAGES: list[dict[str, str]] = [
    {"role": "user", "content": "Hello"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Build a config mapping with test DeepSeek values set."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", TEST_API_BASE)
    monkeypatch.setenv("DEEPSEEK_MODEL", TEST_MODEL)
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "4096")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DEEPSEEK_TRUST_ENV", "false")

    config_obj = create_config("testing")
    return config_obj.to_mapping()


def _ok_response(content: str = "Hello! I'm an AI assistant.") -> dict[str, Any]:
    """Return a minimal Chat Completions success response."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


def _run_async(coro: Any) -> Any:
    """Run a coroutine synchronously in a test."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1.  Request is sent to /chat/completions with correct fields
# ---------------------------------------------------------------------------


def test_sends_request_to_chat_completions(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client must POST to <api_base>/chat/completions."""
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    assert len(captured) == 1
    assert captured[0].url.path.endswith("/chat/completions")


def test_request_uses_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    body = json.loads(captured[0].content)
    assert body["model"] == TEST_MODEL


def test_request_contains_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    body = json.loads(captured[0].content)
    assert body["messages"] == TEST_MESSAGES


def test_request_contains_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    body = json.loads(captured[0].content)
    assert body["max_tokens"] == 4096


# ---------------------------------------------------------------------------
# 2.  Authorization header
# ---------------------------------------------------------------------------


def test_authorization_header_uses_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    auth = captured[0].headers.get("Authorization")
    assert auth == f"Bearer {TEST_API_KEY}"


# ---------------------------------------------------------------------------
# 3.  Parse normal text response
# ---------------------------------------------------------------------------


def test_returns_assistant_content(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_reply = "I am DeepSeek, how can I help you?"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_response(content=expected_reply))

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> dict[str, Any]:
        async with DeepSeekClient(config=config, transport=transport) as client:
            return await client.create_chat_completion(messages=TEST_MESSAGES)

    result = _run_async(run())

    assert result["content"] == expected_reply


# ---------------------------------------------------------------------------
# 4.  API Base with trailing slash
# ---------------------------------------------------------------------------


def test_api_base_with_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trailing slash on API Base must not produce a double-slash URL."""
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("DEEPSEEK_API_BASE", "https://api.example.invalid/")
    monkeypatch.setenv("DEEPSEEK_MODEL", TEST_MODEL)
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "4096")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DEEPSEEK_TRUST_ENV", "false")
    config_obj = create_config("testing")
    config = config_obj.to_mapping()

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    url = str(captured[0].url)
    assert "//chat/completions" not in url, f"Double slash in URL: {url}"
    assert url.endswith("/chat/completions")


# ---------------------------------------------------------------------------
# 5.  No real network access
# ---------------------------------------------------------------------------


def test_does_not_access_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Using MockTransport guarantees no real HTTP calls."""
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_ok_response())

    transport = httpx.MockTransport(handler)
    config = _make_config(monkeypatch)

    from app.services.deepseek_client import DeepSeekClient

    async def run() -> None:
        async with DeepSeekClient(config=config, transport=transport) as client:
            await client.create_chat_completion(messages=TEST_MESSAGES)

    _run_async(run())

    assert call_count == 1
