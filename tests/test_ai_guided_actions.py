"""Tests for the guided AI student action feature (phase 1: create_student).

Covers the structured action model, the in-process AIActionStore, the
action_id-based query/confirm/cancel endpoints, backward compatibility of the
existing chat confirmation contract, single-execution semantics, and log
redaction.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import pytest

from app import create_app
from app.services.ai_action import (
    CANCELLED,
    CREATE_STUDENT,
    EXECUTING,
    EXPIRED,
    FAILED,
    PENDING,
    SUCCEEDED,
    filter_student_payload,
    target_page_for,
)
from app.services.ai_action_store import (
    AIActionExpiredError,
    AIActionNotExecutableError,
    AIActionNotFoundError,
    AIActionStore,
)


# ---------------------------------------------------------------------------
# Service-level fakes
# ---------------------------------------------------------------------------


class FakeConfirmation:
    """Records token payloads and returns a fixed token."""

    def __init__(self, token: str = "signed-token-1") -> None:
        self.token = token
        self.received_payloads: list[dict[str, Any]] = []

    def create_token(self, payload: dict[str, object]) -> str:
        self.received_payloads.append(dict(payload))
        return self.token


class FakeDeepSeekClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)

    async def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.responses.pop(0) if self.responses else {"content": "默认回复"}


class FakeMCPToolAdapter:
    def __init__(self) -> None:
        self.invoke_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def discover_tools(self) -> list[dict[str, Any]]:
        return []

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return []

    @property
    def allowed_tool_names(self):
        return set()

    async def invoke_tool(self, tool_name: str, arguments: Any) -> dict[str, Any]:
        self.invoke_count += 1
        return {"success": True, "data": {}}


def _run_async(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def _write_response(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [{
            "id": "tc-1",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        }],
    }


def _build_service(
    *,
    action_store: AIActionStore,
    tool: str = "add_student",
    arguments: dict[str, Any] | None = None,
    action_id: str | None = None,
    confirmation: FakeConfirmation | None = None,
):
    from app.services.ai_chat_service import AIChatService

    arguments = arguments if arguments is not None else {
        "student_number": "20260001",
        "name": "张三",
        "major": "计算机科学",
        "year_level": "大一",
        "score": 88,
    }
    return AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient([_write_response(tool, arguments)]),
        mcp_adapter_factory=FakeMCPToolAdapter,
        action_confirmation=confirmation or FakeConfirmation(),
        action_id_factory=(lambda: action_id) if action_id else None,
        action_store=action_store,
        action_ttl_seconds=120,
    )


# ---------------------------------------------------------------------------
# Service-level guided action generation
# ---------------------------------------------------------------------------


def test_chat_create_student_returns_guided_action_json() -> None:
    store = AIActionStore()
    action_id = str(uuid.uuid4())
    service = _build_service(action_store=store, action_id=action_id)

    result = _run_async(service.chat([{"role": "user", "content": "新增学生"}], user_id=7))

    assert result["success"] is True
    assert result["requires_confirmation"] is True
    action = result["action"]
    assert action["action_id"] == action_id
    assert action["action_type"] == CREATE_STUDENT
    assert action["status"] == PENDING
    assert action["requires_confirmation"] is True
    assert action["target_page"] == "/students"
    assert action["payload"] == {
        "student_number": "20260001",
        "name": "张三",
        "major": "计算机科学",
        "year_level": "大一",
        "score": 88,
    }
    entry = store.get_for_user(action_id, 7)
    assert entry is not None
    assert entry["tool_name"] == "add_student"
    assert entry["user_id"] == 7
    assert entry["confirmation_token"] == "signed-token-1"


def test_chat_preserves_existing_confirmation_contract() -> None:
    store = AIActionStore()
    service = _build_service(action_store=store, confirmation=FakeConfirmation(token="signed"))

    result = _run_async(service.chat([{"role": "user", "content": "新增学生"}], user_id=1))

    assert result["confirmation_token"] == "signed"
    assert result["pending_action"]["summary"] == "新增学生"
    assert "safe_arguments" in result["pending_action"]
    assert result["reply"] == "已准备添加学生，请确认。"


def test_chat_non_create_write_has_no_guided_action() -> None:
    store = AIActionStore()
    service = _build_service(
        action_store=store,
        tool="update_student",
        arguments={"student_id": 1, "name": "新名"},
    )

    result = _run_async(service.chat([{"role": "user", "content": "修改"}], user_id=1))

    assert "action" not in result
    assert result["requires_confirmation"] is True
    assert result["confirmation_token"] == "signed-token-1"


def test_action_id_is_unpredictable_and_unique() -> None:
    store = AIActionStore()
    ids: set[str] = set()
    for _ in range(5):
        service = _build_service(action_store=store)
        result = _run_async(service.chat([{"role": "user", "content": "新增"}], user_id=1))
        ids.add(result["action"]["action_id"])
    assert len(ids) == 5


def test_action_json_contains_no_executable_content() -> None:
    store = AIActionStore()
    injected = {
        "student_number": "20260001",
        "name": "张三",
        "onclick": "alert(1)",
        "script": "alert(1)",
        "css": "body{display:none}",
        "sql": "DROP TABLE students",
        "url": "http://evil.example",
        "selector": "#x",
    }
    service = _build_service(action_store=store, arguments=injected)

    result = _run_async(service.chat([{"role": "user", "content": "新增"}], user_id=1))

    payload = result["action"]["payload"]
    assert payload == {"student_number": "20260001", "name": "张三"}
    assert "confirmation_token" not in result["action"]


def test_target_page_is_fixed_server_mapping() -> None:
    assert target_page_for(CREATE_STUDENT) == "/students"
    assert target_page_for("anything-else") == "/students"


def test_filter_student_payload_drops_unknown_fields() -> None:
    payload = filter_student_payload({
        "student_number": "0001",
        "name": "李四",
        "email": "a@b.c",
        "secret": "x",
    })
    assert payload == {"student_number": "0001", "name": "李四", "email": "a@b.c"}


# ---------------------------------------------------------------------------
# AIActionStore
# ---------------------------------------------------------------------------


def _create(store: AIActionStore, *, user_id: int = 1, expires_at: float | None = None, action_id: str | None = None) -> str:
    aid = action_id or str(uuid.uuid4())
    store.create(
        action_id=aid,
        action_type=CREATE_STUDENT,
        tool_name="add_student",
        arguments={"student_number": "0001", "name": "李四"},
        payload={"student_number": "0001", "name": "李四"},
        token=f"token-{aid}",
        user_id=user_id,
        expires_at=expires_at if expires_at is not None else time.time() + 120,
    )
    return aid


def test_store_binds_user_and_hides_other_users() -> None:
    store = AIActionStore()
    aid = _create(store, user_id=10)
    assert store.get_for_user(aid, 10) is not None
    assert store.get_for_user(aid, 99) is None
    assert store.safe_view(aid, 99) is None


def test_store_safe_view_excludes_token_and_internals() -> None:
    store = AIActionStore()
    aid = _create(store, user_id=1)
    view = store.safe_view(aid, 1)
    assert view["action_id"] == aid
    assert view["action_type"] == CREATE_STUDENT
    assert view["status"] == PENDING
    assert view["target_page"] == "/students"
    assert "confirmation_token" not in view
    assert "tool_name" not in view
    assert "arguments" not in view


def test_store_begin_execution_is_single_use() -> None:
    store = AIActionStore()
    aid = _create(store)
    assert store.begin_execution(aid) == f"token-{aid}"
    with pytest.raises(AIActionNotExecutableError):
        store.begin_execution(aid)
    assert store.get(aid)["status"] == EXECUTING


def test_store_begin_execution_expired_raises() -> None:
    store = AIActionStore()
    aid = _create(store, expires_at=10.0)
    with pytest.raises(AIActionExpiredError):
        store.begin_execution(aid, now=20.0)
    assert store.get(aid)["status"] == EXPIRED


def test_store_cancel_prevents_execution() -> None:
    store = AIActionStore()
    aid = _create(store, user_id=1)
    assert store.cancel(aid, 1) is True
    with pytest.raises(AIActionNotExecutableError):
        store.begin_execution(aid)
    assert store.get(aid)["status"] == CANCELLED


def test_store_cancel_other_user_raises() -> None:
    store = AIActionStore()
    aid = _create(store, user_id=1)
    with pytest.raises(AIActionNotFoundError):
        store.cancel(aid, 99)


def test_store_mark_succeeded_only_from_executing() -> None:
    store = AIActionStore()
    aid = _create(store)
    store.mark_succeeded(aid, {"id": 1})
    assert store.get(aid)["status"] == PENDING
    store.begin_execution(aid)
    store.mark_succeeded(aid, {"id": 1})
    assert store.get(aid)["status"] == SUCCEEDED


def test_store_mark_failed_records_error() -> None:
    store = AIActionStore()
    aid = _create(store)
    store.begin_execution(aid)
    store.mark_failed(aid, "duplicate")
    entry = store.get(aid)
    assert entry["status"] == FAILED
    assert entry["error"] == "duplicate"


def test_store_expire_stale() -> None:
    store = AIActionStore()
    a1 = _create(store, expires_at=10.0)
    a2 = _create(store, expires_at=1000.0)
    assert store.expire_stale(now=50.0) == 1
    assert store.get(a1)["status"] == EXPIRED
    assert store.get(a2)["status"] == PENDING


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------


class FakeConfirmService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.result: dict[str, Any] = {
            "success": True,
            "reply": "新增学生成功。",
            "requires_confirmation": False,
            "pending_action": None,
            "action_result": {"success": True, "data": {"id": 1}},
        }

    async def confirm_action(self, confirmation_token: str) -> dict[str, Any]:
        self.calls.append(confirmation_token)
        return dict(self.result)


def _app() -> Any:
    return create_app("testing", config_overrides={
        "TESTING": True,
        "SECRET_KEY": "test-secret-not-for-production",
        "AI_WRITE_CONFIRMATION": True,
        "BOOTSTRAP_DEFAULT_USERS_ENABLED": True,
        "BOOTSTRAP_VIEWER_USERNAME": "viewer",
        "BOOTSTRAP_VIEWER_PASSWORD": "viewer1",
        "BOOTSTRAP_STAFF_USERNAME": "staff",
        "BOOTSTRAP_STAFF_PASSWORD": "staff1",
        "BOOTSTRAP_ADMIN_USERNAME": "admin",
        "BOOTSTRAP_ADMIN_PASSWORD": "admin1",
    }, load_env=False)


def _user_id(app: Any, role: str) -> int:
    return app.extensions["user_service_factory"]().get_user_by_username(role)["id"]


def _login(client: Any, app: Any, role: str = "admin") -> None:
    user = app.extensions["user_service_factory"]().get_user_by_username(role)
    with client.session_transaction() as session:
        session["user_id"] = user["id"]
        session["auth_version"] = user["auth_version"]
        session["csrf_token"] = "test-csrf-token"


def _seed(app: Any, *, user_id: int, expires_at: float | None = None, action_id: str | None = None) -> str:
    aid = action_id or str(uuid.uuid4())
    app.extensions["ai_action_store"].create(
        action_id=aid,
        action_type=CREATE_STUDENT,
        tool_name="add_student",
        arguments={"student_number": "20260001", "name": "张三"},
        payload={"student_number": "20260001", "name": "张三"},
        token=f"token-{aid}",
        user_id=user_id,
        expires_at=expires_at if expires_at is not None else time.time() + 120,
    )
    return aid


# ---------------------------------------------------------------------------
# GET /api/chat/actions/<action_id>
# ---------------------------------------------------------------------------


def test_get_action_returns_safe_data_no_token() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"))

    response = client.get(f"/api/chat/actions/{aid}")

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "no-store"
    data = response.get_json()["data"]
    assert data["action_id"] == aid
    assert data["action_type"] == CREATE_STUDENT
    assert data["status"] == PENDING
    assert data["target_page"] == "/students"
    assert "confirmation_token" not in data
    assert "tool_name" not in data
    assert "arguments" not in data
    assert "confirmation_token" not in response.get_data(as_text=True)


def test_get_action_other_user_404() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "staff"))

    response = client.get(f"/api/chat/actions/{aid}")

    assert response.status_code == 404
    assert "confirmation_token" not in response.get_data(as_text=True)


def test_get_action_not_found_404() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")

    response = client.get(f"/api/chat/actions/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_action_non_uuid_path_does_not_match() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")

    response = client.get("/api/chat/actions/not-a-uuid")

    assert response.status_code in (404, 405)


def test_get_action_expired_is_not_confirmable() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"), expires_at=time.time() - 10)
    app.extensions["ai_action_store"].expire_stale()

    response = client.get(f"/api/chat/actions/{aid}")

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == EXPIRED


def test_get_action_requires_login() -> None:
    app = _app()
    client = app.test_client()

    response = client.get(f"/api/chat/actions/{uuid.uuid4()}")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/chat/actions/<action_id>/confirm
# ---------------------------------------------------------------------------


def test_confirm_guided_action_executes_once() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["action_id"] == aid
    assert data["status"] == SUCCEEDED
    assert data["action_result"]["data"]["id"] == 1
    assert fake.calls == [f"token-{aid}"]
    assert app.extensions["ai_action_store"].get(aid)["status"] == SUCCEEDED

    # A second confirmation must not execute again.
    second = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})
    assert second.status_code == 409
    assert fake.calls == [f"token-{aid}"]


def test_confirm_guided_action_other_user_404() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "staff"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 404
    assert fake.calls == []


def test_confirm_guided_action_cancelled_rejected() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    uid = _user_id(app, "admin")
    aid = _seed(app, user_id=uid)
    app.extensions["ai_action_store"].cancel(aid, uid)

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 409
    assert fake.calls == []


def test_confirm_guided_action_expired_rejected() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"), expires_at=time.time() - 10)

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ai_action_expired"
    assert fake.calls == []


def test_confirm_guided_action_requires_csrf() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "wrong"})

    assert response.status_code == 403
    assert fake.calls == []


def test_confirm_ignores_client_submitted_fields() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={
        "payload": {"student_number": "hacked"},
        "tool_name": "delete_student",
        "arguments": {"student_id": 999},
        "action_id": "other-action",
        "summary": "hacked",
    }, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 200
    assert fake.calls == [f"token-{aid}"]
    assert app.extensions["ai_action_store"].get(aid)["tool_name"] == "add_student"


def test_confirm_guided_action_failure_marks_failed() -> None:
    app = _app()
    fake = FakeConfirmService()
    fake.result = {
        "success": False,
        "reply": "操作执行失败",
        "requires_confirmation": False,
        "pending_action": None,
        "action_result": {"success": False, "error": {"code": "duplicate"}},
    }
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == FAILED
    assert data["reply"] == "操作执行失败"
    assert app.extensions["ai_action_store"].get(aid)["status"] == FAILED


def test_confirm_guided_action_execution_error_is_safe() -> None:
    from app.services.ai_errors import AIConfirmationExecutionError

    app = _app()

    class RaisingConfirmService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def confirm_action(self, confirmation_token: str) -> dict[str, Any]:
            self.calls.append(confirmation_token)
            raise AIConfirmationExecutionError()

    fake = RaisingConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "admin"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "ai_confirmation_execution_failed"
    assert fake.calls == [f"token-{aid}"]
    assert app.extensions["ai_action_store"].get(aid)["status"] == FAILED


def test_confirm_guided_action_viewer_denied() -> None:
    app = _app()
    fake = FakeConfirmService()
    app.extensions["ai_chat_service_factory"] = lambda: fake
    client = app.test_client()
    _login(client, app, "viewer")
    aid = _seed(app, user_id=_user_id(app, "viewer"))

    response = client.post(f"/api/chat/actions/{aid}/confirm", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 403
    assert fake.calls == []


# ---------------------------------------------------------------------------
# POST /api/chat/actions/<action_id>/cancel
# ---------------------------------------------------------------------------


def test_cancel_guided_action() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")
    uid = _user_id(app, "admin")
    aid = _seed(app, user_id=uid)

    response = client.post(f"/api/chat/actions/{aid}/cancel", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 200
    assert response.get_json()["data"]["cancelled"] is True
    assert app.extensions["ai_action_store"].get(aid)["status"] == CANCELLED


def test_cancel_guided_action_other_user_404() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")
    aid = _seed(app, user_id=_user_id(app, "staff"))

    response = client.post(f"/api/chat/actions/{aid}/cancel", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 404


def test_cancel_executed_action_rejected() -> None:
    app = _app()
    client = app.test_client()
    _login(client, app, "admin")
    uid = _user_id(app, "admin")
    aid = _seed(app, user_id=uid)
    app.extensions["ai_action_store"].begin_execution(aid)

    response = client.post(f"/api/chat/actions/{aid}/cancel", json={}, headers={"X-CSRF-Token": "test-csrf-token"})

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Log redaction
# ---------------------------------------------------------------------------


def test_guided_flow_logs_do_not_contain_token_or_student_record(caplog: pytest.LogCaptureFixture) -> None:
    store = AIActionStore()
    confirmation = FakeConfirmation(token="super-secret-token-value")
    service = _build_service(action_store=store, confirmation=confirmation)
    with caplog.at_level("INFO"):
        result = _run_async(service.chat([{"role": "user", "content": "新增学生"}], user_id=1))
    caplog_text = caplog.text
    assert "super-secret-token-value" not in caplog_text
    assert "张三" not in caplog_text
    assert "20260001" not in caplog_text
    assert "confirmation_token" not in result["action"]
