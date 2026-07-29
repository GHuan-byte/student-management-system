"""Tests for the initial POST /api/chat route."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from app import create_app
from app.services.ai_errors import AIClientError


class FakeAIChatService:
    """In-memory chat service that records the normalized route input."""

    def __init__(self, result: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.result = result or {
            "success": True,
            "reply": "当前共有 42 名学生。",
            "requires_confirmation": False,
            "pending_action": None,
        }
        self.error = error
        self.calls: list[list[dict[str, object]]] = []

    async def chat(self, messages: list[dict[str, object]]) -> dict[str, object]:
        self.calls.append(copy.deepcopy(messages))
        if self.error is not None:
            raise self.error
        return dict(self.result)


def _client(service: FakeAIChatService, **overrides: object):
    config = {
        "TESTING": True,
        "AI_MAX_HISTORY_MESSAGES": 2,
        "AI_MAX_MESSAGE_LENGTH": 20,
    }
    config.update(overrides)
    app = create_app("testing", config_overrides=config, load_env=False)
    app.extensions["ai_chat_service_factory"] = lambda: service
    return app.test_client()


def _assert_validation(response: Any) -> None:
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "validation_error"


def test_post_chat_returns_unified_reply_and_normalized_messages() -> None:
    service = FakeAIChatService()
    client = _client(service)

    response = client.post("/api/chat", json={"messages": [
        {"role": "assistant", "content": "你好", "reasoning_content": "private"},
        {"role": "user", "content": "查询学生总数", "tool_calls": []},
    ]})

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {
            "reply": "当前共有 42 名学生。",
            "requires_confirmation": False,
            "pending_action": None,
        },
        "message": "",
        "error": None,
        "meta": {},
    }
    assert service.calls == [[
        {"role": "assistant", "content": "你好"},
        {"role": "user", "content": "查询学生总数"},
    ]]


@pytest.mark.parametrize("body, content_type", [
    ("not-json", "text/plain"),
    ("{", "application/json"),
    ("[]", "application/json"),
])
def test_post_chat_rejects_non_object_json(body: str, content_type: str) -> None:
    service = FakeAIChatService()
    response = _client(service).post("/api/chat", data=body, content_type=content_type)
    _assert_validation(response)
    assert service.calls == []


@pytest.mark.parametrize("payload", [
    {},
    {"messages": "not-an-array"},
    {"messages": []},
    {"messages": ["not-an-object"]},
    {"messages": [{"content": "hi"}]},
    {"messages": [{"role": "system", "content": "hi"}]},
    {"messages": [{"role": "tool", "content": "hi"}]},
    {"messages": [{"role": "developer", "content": "hi"}]},
    {"messages": [{"role": "user"}]},
    {"messages": [{"role": "user", "content": 1}]},
    {"messages": [{"role": "user", "content": ""}]},
    {"messages": [{"role": "user", "content": "   "}]},
    {"messages": [{"role": "assistant", "content": "hi"}]},
])
def test_post_chat_rejects_invalid_messages(payload: dict[str, object]) -> None:
    service = FakeAIChatService()
    response = _client(service).post("/api/chat", json=payload)
    _assert_validation(response)
    assert service.calls == []


def test_post_chat_rejects_message_over_configured_limit() -> None:
    service = FakeAIChatService()
    response = _client(service).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "x" * 21}]},
    )
    _assert_validation(response)
    assert service.calls == []


def test_post_chat_validates_entire_history_before_truncating() -> None:
    service = FakeAIChatService()
    response = _client(service).post("/api/chat", json={"messages": [
        {"role": "system", "content": "must not be skipped"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "query"},
    ]})
    _assert_validation(response)
    assert service.calls == []


def test_post_chat_truncates_only_after_validation_without_mutating_request() -> None:
    service = FakeAIChatService()
    request_payload = {"messages": [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "middle"},
        {"role": "user", "content": "new"},
    ]}
    original = copy.deepcopy(request_payload)

    response = _client(service).post("/api/chat", json=request_payload)

    assert response.status_code == 200
    assert service.calls == [[
        {"role": "assistant", "content": "middle"},
        {"role": "user", "content": "new"},
    ]]
    assert request_payload == original


def test_post_chat_preserves_pending_action_without_recreating_it() -> None:
    service = FakeAIChatService(result={
        "success": True,
        "reply": "需要确认后才能执行：新增学生",
        "requires_confirmation": True,
        "confirmation_token": "signed-token",
        "pending_action": {"summary": "新增学生", "safe_arguments": "{}"},
    })
    response = _client(service).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "新增学生"}]},
    )

    data = response.get_json()["data"]
    assert data["requires_confirmation"] is True
    assert data["pending_action"] == {"summary": "新增学生", "safe_arguments": "{}"}
    assert data["confirmation_token"] == "signed-token"
    assert len(service.calls) == 1


def test_post_chat_maps_ai_client_error_to_safe_json() -> None:
    class SafeError(AIClientError):
        code = "ai_not_configured"
        safe_message = "AI 服务配置不完整"

    service = FakeAIChatService(error=SafeError())
    response = _client(service).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "查询"}]},
    )
    payload = response.get_json()
    assert response.status_code == 500
    assert payload["error"]["code"] == "ai_not_configured"
    assert payload["message"] == "AI 服务配置不完整"


def test_post_chat_maps_unknown_error_without_leaking_request() -> None:
    service = FakeAIChatService(error=RuntimeError("traceback token=secret 张三"))
    response = _client(service).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "张三的资料"}]},
    )
    payload = response.get_json()
    assert response.status_code == 500
    assert payload["error"]["code"] == "internal_error"
    assert all(value not in str(payload) for value in ("traceback", "secret", "张三"))
