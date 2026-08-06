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

    async def chat(self, messages: list[dict[str, object]], *, user_id: object = None) -> dict[str, object]:
        self.calls.append(copy.deepcopy(messages))
        if self.error is not None:
            raise self.error
        return dict(self.result)

    async def confirm_action(self, confirmation_token: str) -> dict[str, object]:
        self.confirm_calls.append(confirmation_token)
        if self.confirm_error is not None:
            raise self.confirm_error
        return dict(self.confirm_result)


def _client(service: FakeAIChatService, role: str = "admin", **overrides: object):
    config = {
        "TESTING": True,
        "AI_MAX_HISTORY_MESSAGES": 2,
        "AI_MAX_MESSAGE_LENGTH": 20,
        "SECRET_KEY": "test-secret-not-for-production",
        "AI_WRITE_CONFIRMATION": False,
        "BOOTSTRAP_DEFAULT_USERS_ENABLED": True,
        "BOOTSTRAP_VIEWER_USERNAME": "viewer",
        "BOOTSTRAP_VIEWER_PASSWORD": "viewer1",
        "BOOTSTRAP_STAFF_USERNAME": "staff",
        "BOOTSTRAP_STAFF_PASSWORD": "staff1",
        "BOOTSTRAP_ADMIN_USERNAME": "admin",
        "BOOTSTRAP_ADMIN_PASSWORD": "admin1",
    }
    config.update(overrides)
    app = create_app("testing", config_overrides=config, load_env=False)
    app.extensions["ai_chat_service_factory"] = lambda: service
    client = app.test_client()
    user = app.extensions["user_service_factory"]().get_user_by_username(role)
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["auth_version"] = user["auth_version"]
        session["csrf_token"] = "test-csrf-token"
    return AuthenticatedClient(client)


def _pending_write_result(app, tool_name: str, action_id: str = "action-1") -> dict[str, object]:
    token = app.extensions["ai_action_confirmation"].create_token({
        "tool_name": tool_name,
        "arguments": {"student_id": 1},
        "action_id": action_id,
    })
    return {
        "success": True,
        "reply": "requires confirmation",
        "requires_confirmation": True,
        "confirmation_token": token,
        "pending_action": {"summary": tool_name, "safe_arguments": "{}"},
    }


class AuthenticatedClient:
    def __init__(self, client):
        self._client = client

    def __getattr__(self, name: str):
        return getattr(self._client, name)

    @property
    def application(self):
        return self._client.application

    def post(self, *args: object, **kwargs: object):
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("X-CSRF-Token", "test-csrf-token")
        return self._client.post(*args, headers=headers, **kwargs)

    def get(self, *args: object, **kwargs: object):
        return self._client.get(*args, **kwargs)


def _authenticated_client_for_app(app):
    client = app.test_client()
    service = app.extensions["user_service_factory"]()
    user = service.get_user_by_username("route-admin") or service.create_user("route-admin", "secret1", "admin")
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["auth_version"] = user["auth_version"]
        session["csrf_token"] = "test-csrf-token"
    return AuthenticatedClient(client)


def _assert_validation(response: Any) -> None:
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "validation_error"


def test_unconfigured_chat_returns_503_before_mcp_or_deepseek() -> None:
    """Route maps the service short-circuit without constructing dependencies."""
    from app.services.ai_chat_service import AIChatService

    deepseek_factory_calls = 0
    adapter_factory_calls = 0

    def deepseek_factory() -> object:
        nonlocal deepseek_factory_calls
        deepseek_factory_calls += 1
        raise AssertionError("DeepSeek must not be created")

    def adapter_factory() -> object:
        nonlocal adapter_factory_calls
        adapter_factory_calls += 1
        raise AssertionError("MCP adapter must not be created")

    app = create_app(
        "testing",
        config_overrides={
            "AI_CONFIGURED": False,
            "AI_MAX_HISTORY_MESSAGES": 2,
            "AI_MAX_MESSAGE_LENGTH": 20,
        },
        load_env=False,
    )
    app.extensions["ai_chat_service_factory"] = lambda: AIChatService(
        deepseek_client_factory=deepseek_factory,
        mcp_adapter_factory=adapter_factory,
        ai_configured=app.config["AI_CONFIGURED"],
    )

    response = _authenticated_client_for_app(app).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "test"}]}
    )
    payload = response.get_json()

    assert response.status_code == 503
    assert payload["success"] is False
    assert payload["error"]["code"] == "ai_not_configured"
    assert payload["error"]["code"] != "internal_error"
    assert all(secret not in str(payload) for secret in ("api_key", "api_base", "model", "traceback"))
    assert deepseek_factory_calls == 0
    assert adapter_factory_calls == 0


def test_app_factory_short_circuits_unconfigured_chat_before_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production factory injects AI_CONFIGURED into AIChatService."""
    import app.services.deepseek_client as deepseek_module
    import app.services.mcp_tool_adapter as adapter_module

    deepseek_constructions = 0
    adapter_constructions = 0

    class RaisingDeepSeekClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            nonlocal deepseek_constructions
            deepseek_constructions += 1
            raise AssertionError("DeepSeek must not be constructed")

    class RaisingMCPToolAdapter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            nonlocal adapter_constructions
            adapter_constructions += 1
            raise AssertionError("MCP adapter must not be constructed")

    monkeypatch.setattr(deepseek_module, "DeepSeekClient", RaisingDeepSeekClient)
    monkeypatch.setattr(adapter_module, "MCPToolAdapter", RaisingMCPToolAdapter)
    app = create_app(
        "testing",
        config_overrides={
            "AI_CONFIGURED": False,
            "AI_MAX_HISTORY_MESSAGES": 2,
            "AI_MAX_MESSAGE_LENGTH": 20,
        },
        load_env=False,
    )

    response = _authenticated_client_for_app(app).post(
        "/api/chat", json={"messages": [{"role": "user", "content": "test"}]}
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "ai_not_configured"
    assert deepseek_constructions == 0
    assert adapter_constructions == 0


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


def test_viewer_chat_write_action_does_not_return_confirmation_token() -> None:
    service = FakeAIChatService()
    client = _client(service, role="viewer", AI_WRITE_CONFIRMATION=True)
    service.result = _pending_write_result(client.application, "add_student", "viewer-add")

    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "add"}]})

    assert response.status_code == 403
    data = response.get_json().get("data")
    assert not data or "confirmation_token" not in data
    assert "confirmation_token" not in response.get_data(as_text=True)


def test_staff_chat_delete_action_does_not_return_confirmation_token() -> None:
    service = FakeAIChatService()
    client = _client(service, role="staff", AI_WRITE_CONFIRMATION=True)
    service.result = _pending_write_result(client.application, "delete_student", "staff-delete")

    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "delete"}]})

    assert response.status_code == 403
    data = response.get_json().get("data")
    assert not data or "confirmation_token" not in data
    assert "confirmation_token" not in response.get_data(as_text=True)


def test_staff_chat_update_action_returns_confirmation_token() -> None:
    service = FakeAIChatService()
    client = _client(service, role="staff", AI_WRITE_CONFIRMATION=True)
    service.result = _pending_write_result(client.application, "update_student", "staff-update")

    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "update"}]})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["requires_confirmation"] is True
    assert isinstance(data["confirmation_token"], str)
    assert data["pending_action"]["summary"] == "update_student"


def test_admin_chat_delete_action_returns_confirmation_token() -> None:
    service = FakeAIChatService()
    client = _client(service, role="admin", AI_WRITE_CONFIRMATION=True)
    service.result = _pending_write_result(client.application, "batch_delete_students", "admin-delete")

    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "delete"}]})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["requires_confirmation"] is True
    assert isinstance(data["confirmation_token"], str)
    assert data["pending_action"]["summary"] == "batch_delete_students"


@pytest.mark.parametrize("tool_name", ["add_student", "update_student", "delete_student"])
def test_viewer_chat_write_action_denial_records_safe_security_event(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
) -> None:
    service = FakeAIChatService()
    client = _client(service, role="viewer", AI_WRITE_CONFIRMATION=True)
    service.result = _pending_write_result(client.application, tool_name, f"viewer-{tool_name}")
    events = []
    monkeypatch.setattr(
        "app.routes.chat.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
        raising=False,
    )
    token = service.result["confirmation_token"]
    user = client.application.extensions["user_service_factory"]().get_user_by_username("viewer")

    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "write"}]})

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert "confirmation_token" not in body
    assert "pending_action" not in body
    assert events == [(
        "authorization_denied",
            {
                "user_id": user["id"],
                "username": "viewer",
            "role": "viewer",
            "endpoint": "chat.chat",
            "method": "POST",
            "tool_name": tool_name,
            "outcome": "denied",
            "reason": "ai_pending_action_forbidden",
        },
    )]
    event_text = str(events)
    assert token not in event_text
    assert "student_id" not in event_text
    assert "write" not in event_text


@pytest.mark.parametrize("tool_name", ["delete_student", "batch_delete_students"])
def test_staff_chat_delete_action_denial_records_safe_security_event(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
) -> None:
    service = FakeAIChatService()
    client = _client(service, role="staff", AI_WRITE_CONFIRMATION=True)
    service.result = _pending_write_result(client.application, tool_name, f"staff-{tool_name}")
    events = []
    monkeypatch.setattr(
        "app.routes.chat.log_security_event",
        lambda event, metadata=None: events.append((event, metadata or {})),
        raising=False,
    )
    token = service.result["confirmation_token"]
    user = client.application.extensions["user_service_factory"]().get_user_by_username("staff")

    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "delete"}]})

    assert response.status_code == 403
    assert "confirmation_token" not in response.get_data(as_text=True)
    assert events == [(
        "authorization_denied",
            {
                "user_id": user["id"],
                "username": "staff",
            "role": "staff",
            "endpoint": "chat.chat",
            "method": "POST",
            "tool_name": tool_name,
            "outcome": "denied",
            "reason": "ai_pending_action_forbidden",
        },
    )]
    event_text = str(events)
    assert token not in event_text
    assert "student_id" not in event_text


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


def test_confirm_failure_keeps_safe_envelope_without_success_reply() -> None:
    """A business failure remains an HTTP response but is visible as failure."""
    service = FakeAIChatService()
    service.confirm_result = {
        "success": False,
        "reply": "操作执行失败，请检查请求参数后重新发起。",
        "requires_confirmation": False,
        "pending_action": None,
        "action_result": {
            "success": False,
            "error": {"code": "validation_error"},
        },
    }

    response = _client(service).post(
        "/api/chat/actions/confirm", json={"confirmation_token": "signed-token"},
    )

    payload = response.get_json()
    public_output = str(payload)
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["reply"] == "操作执行失败，请检查请求参数后重新发起。"
    assert "成功" not in payload["data"]["reply"]
    assert payload["data"]["action_result"] == {
        "success": False,
        "error": {"code": "validation_error"},
    }
    assert payload["error"] is None
    assert "internal_error" not in public_output
    assert service.confirm_calls == ["signed-token"]


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
