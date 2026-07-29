"""Tests for the initial POST /api/chat route."""

from __future__ import annotations

import copy
from typing import Any

import httpx
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
        self.confirm_calls: list[str] = []
        self.confirm_result: dict[str, object] = {
            "success": True,
            "reply": "新增学生成功。",
            "requires_confirmation": False,
            "pending_action": None,
            "action_result": {"success": True, "data": {"id": 1}},
        }
        self.confirm_error: Exception | None = None

    async def chat(self, messages: list[dict[str, object]]) -> dict[str, object]:
        self.calls.append(copy.deepcopy(messages))
        if self.error is not None:
            raise self.error
        return dict(self.result)

    async def confirm_action(self, confirmation_token: str) -> dict[str, object]:
        self.confirm_calls.append(confirmation_token)
        if self.confirm_error is not None:
            raise self.confirm_error
        return dict(self.confirm_result)


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
    assert response.status_code == 503
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


def test_confirm_returns_safe_envelope_and_receives_only_token() -> None:
    service = FakeAIChatService()
    response = _client(service).post("/api/chat/actions/confirm", json={
        "confirmation_token": "signed-token",
        "tool_name": "delete_student",
        "arguments": {"student_id": 999},
        "action_id": "browser-value",
        "summary": "browser-value",
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"] == {
        "reply": "新增学生成功。",
        "requires_confirmation": False,
        "pending_action": None,
        "action_result": {"success": True, "data": {"id": 1}},
    }
    assert service.confirm_calls == ["signed-token"]
    assert service.calls == []
    assert all(key not in str(payload) for key in (
        "confirmation_token", "tool_name", "arguments", "action_id", "reasoning_content",
    ))


@pytest.mark.parametrize("body, content_type", [
    ("not-json", "text/plain"), ("{", "application/json"), ("[]", "application/json"),
])
def test_confirm_rejects_non_object_json(body: str, content_type: str) -> None:
    service = FakeAIChatService()
    response = _client(service).post(
        "/api/chat/actions/confirm", data=body, content_type=content_type,
    )
    _assert_validation(response)
    assert service.confirm_calls == []


@pytest.mark.parametrize("payload", [
    {}, {"confirmation_token": None}, {"confirmation_token": 1},
    {"confirmation_token": ""}, {"confirmation_token": "   "},
])
def test_confirm_rejects_invalid_token_input(payload: dict[str, object]) -> None:
    service = FakeAIChatService()
    response = _client(service).post("/api/chat/actions/confirm", json=payload)
    _assert_validation(response)
    assert service.confirm_calls == []


@pytest.mark.parametrize("error, status", [
    ("AINotConfiguredError", 503), ("AIAuthError", 502), ("AITimeoutError", 504),
    ("AIRateLimitedError", 429), ("AIUpstreamError", 502),
    ("AIInvalidResponseError", 502), ("AIToolRoundLimitError", 400),
    ("AIMultipleWriteActionsError", 400),
])
def test_chat_maps_ai_errors_to_stable_status(error: str, status: int) -> None:
    import app.services.ai_errors as errors
    service = FakeAIChatService(error=getattr(errors, error)())
    response = _client(service).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "query"}]},
    )
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == getattr(errors, error).code


@pytest.mark.parametrize("error, status", [
    ("AIConfirmationNotConfiguredError", 503), ("AIConfirmationInvalidError", 400),
    ("AIConfirmationExpiredError", 400), ("AIConfirmationReplayError", 409),
    ("AIConfirmationExecutionError", 502),
])
def test_confirm_maps_ai_errors_to_stable_status(error: str, status: int) -> None:
    import app.services.ai_errors as errors
    service = FakeAIChatService()
    service.confirm_error = getattr(errors, error)()
    response = _client(service).post(
        "/api/chat/actions/confirm", json={"confirmation_token": "signed-token"},
    )
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == getattr(errors, error).code


def test_confirm_unknown_error_is_safe() -> None:
    service = FakeAIChatService()
    service.confirm_error = RuntimeError("traceback Bearer sk-secret model api-base signed-token")
    response = _client(service).post(
        "/api/chat/actions/confirm", json={"confirmation_token": "signed-token"},
    )
    payload = response.get_json()
    assert response.status_code == 500
    assert payload["error"]["code"] == "internal_error"
    assert all(value not in str(payload) for value in (
        "traceback", "sk-secret", "model", "api-base", "signed-token",
    ))


def test_confirm_response_strips_raw_mcp_diagnostics() -> None:
    service = FakeAIChatService()
    service.confirm_result["action_result"] = {
        "success": True,
        "data": {
            "student": {"id": 1},
            "structured_content": "private",
            "parsed_text": "private",
            "traceback": "private",
            "reasoning_content": "private",
        },
    }
    response = _client(service).post(
        "/api/chat/actions/confirm", json={"confirmation_token": "signed-token"},
    )
    public_output = str(response.get_json())
    assert response.get_json()["data"]["action_result"] == {
        "success": True, "data": {"student": {"id": 1}},
    }
    assert all(key not in public_output for key in (
        "structured_content", "parsed_text", "traceback", "reasoning_content",
    ))


def test_chat_hides_raw_httpx_exception_details() -> None:
    service = FakeAIChatService(error=httpx.ConnectError(
        "Bearer sk-secret https://api.example.invalid/model student message",
    ))
    response = _client(service).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "student message"}]},
    )
    payload = response.get_json()
    assert response.status_code == 500
    assert payload["error"]["code"] == "internal_error"
    assert all(value not in str(payload) for value in (
        "sk-secret", "api.example.invalid", "model", "student message",
    ))


def test_chat_route_paths_are_model_agnostic() -> None:
    service = FakeAIChatService()
    app = _client(service).application
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/chat" in paths
    assert "/api/chat/actions/confirm" in paths
    assert all("deepseek" not in path.lower() and "gpt" not in path.lower() for path in paths)


def test_chat_blueprint_registers_each_post_endpoint_once() -> None:
    service = FakeAIChatService()
    app = _client(service).application
    rules = list(app.url_map.iter_rules())
    chat_rules = [rule for rule in rules if rule.rule in {
        "/api/chat", "/api/chat/actions/confirm",
    }]
    assert len(chat_rules) == 2
    assert all("POST" in rule.methods for rule in chat_rules)
    assert all(rule.endpoint.startswith("chat.") for rule in chat_rules)


def test_chat_get_requests_use_json_error_without_calling_service() -> None:
    service = FakeAIChatService()
    client = _client(service)
    for path in ("/api/chat", "/api/chat/actions/confirm"):
        response = client.get(path)
        assert response.status_code == 405
        assert response.get_json()["error"]["code"] == "method_not_allowed"
    assert service.calls == []
    assert service.confirm_calls == []


def test_create_app_can_register_chat_blueprint_repeatedly() -> None:
    app_one = create_app("testing", load_env=False)
    app_two = create_app("testing", load_env=False)
    for app in (app_one, app_two):
        paths = [rule.rule for rule in app.url_map.iter_rules()]
        assert paths.count("/api/chat") == 1
        assert paths.count("/api/chat/actions/confirm") == 1


def test_health_and_students_routes_remain_registered() -> None:
    service = FakeAIChatService()
    paths = {rule.rule for rule in _client(service).application.url_map.iter_rules()}
    assert "/api/health" in paths
    assert "/api/students" in paths
