"""Tests for AIChatService.confirm_action — confirmed write execution.

RED phase — confirm_action does not exist yet.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest

from app.services.ai_errors import (
    AIConfirmationExpiredError,
    AIConfirmationInvalidError,
    AIConfirmationInvalidPayloadError,
    AIConfirmationNotConfiguredError,
    AIConfirmationReplayError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAFE_KEY = "i-am-a-safe-secret-key-for-testing"
TTL_SECONDS = 300

WRITE_PAYLOAD: dict[str, object] = {
    "tool_name": "add_student",
    "arguments": {"student_number": "0001", "name": "张三"},
    "action_id": "test-uuid-001",
}

UPDATE_PAYLOAD: dict[str, object] = {
    "tool_name": "update_student",
    "arguments": {"student_id": 1, "name": "李四"},
    "action_id": "test-uuid-002",
}

DELETE_PAYLOAD: dict[str, object] = {
    "tool_name": "delete_student",
    "arguments": {"student_id": 42},
    "action_id": "test-uuid-003",
}

READ_PAYLOAD: dict[str, object] = {
    "tool_name": "count_students",
    "arguments": {},
    "action_id": "test-uuid-read",
}

UNKNOWN_PAYLOAD: dict[str, object] = {
    "tool_name": "drop_database",
    "arguments": {},
    "action_id": "test-uuid-unknown",
}

NO_ARGS_PAYLOAD: dict[str, object] = {
    "tool_name": "add_student",
    "arguments": "not-a-dict",
    "action_id": "test-uuid-noargs",
}

EMPTY_ACTION_ID_PAYLOAD: dict[str, object] = {
    "tool_name": "add_student",
    "arguments": {},
    "action_id": "",
}

SUCCESS_RESULT: dict[str, object] = {
    "success": True,
    "data": {"id": 1, "student_number": "0001", "name": "张三"},
}

BUSINESS_ERROR_RESULT: dict[str, object] = {
    "success": False,
    "data": None,
    "message": "学号已存在",
    "error": {"code": "duplicate_student_number", "details": None},
    "meta": {},
}

TECHNICAL_ERROR_RESULT: dict[str, object] = {
    "success": False,
    "data": None,
    "message": "学生数据工具暂时不可用",
    "error": {"code": "mcp_tool_error", "details": None},
    "meta": {},
}


def _make_token(confirmation: Any, payload: dict[str, object]) -> str:
    """Create a signed token from the real AIActionConfirmation."""
    return confirmation.create_token(payload)


def _expired_future() -> int:
    """Return a timestamp far in the future for patching time.time."""
    return 99_999_999_999


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeDeepSeekClient:
    """Fake that records calls and supports preset responses."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.responses = list(responses) if responses else []
        self.call_count = 0
        self.calls: list[list[dict[str, Any]]] = []

    async def create_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.call_count += 1
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return {"content": "默认回复"}


class FakeMCPToolAdapter:
    """Fake that records invocations for confirm_action testing."""

    def __init__(self) -> None:
        self.discover_count = 0
        self.invoke_count = 0
        self.enter_count = 0
        self.exit_count = 0
        self.called_tools: list[str] = []
        self.called_args: list[Any] = []
        self._invoke_results: list[dict[str, Any]] = []

    def add_invoke_result(self, result: dict[str, Any]) -> None:
        self._invoke_results.append(result)

    async def discover_tools(self) -> list[dict[str, Any]]:
        self.discover_count += 1
        return []

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return []

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: str | dict[str, object],
    ) -> dict[str, object]:
        self.invoke_count += 1
        self.called_tools.append(tool_name)
        self.called_args.append(arguments)
        if self._invoke_results:
            return self._invoke_results.pop(0)
        return dict(SUCCESS_RESULT)

    async def __aenter__(self) -> FakeMCPToolAdapter:
        self.enter_count += 1
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.exit_count += 1


class InvokeFailingAdapter(FakeMCPToolAdapter):
    """Fake adapter whose write invocation raises an internal exception."""

    async def invoke_tool(
        self, tool_name: str, arguments: str | dict[str, object],
    ) -> dict[str, object]:
        self.invoke_count += 1
        raise RuntimeError("token=secret-token name=张三 traceback=private")


class DiscoveryFailingAdapter(FakeMCPToolAdapter):
    """Fake adapter whose discovery fails after the token is consumed."""

    async def discover_tools(self) -> list[dict[str, Any]]:
        self.discover_count += 1
        raise RuntimeError("database_path=private")


class ExitFailingAdapter(FakeMCPToolAdapter):
    """Fake adapter whose context exit fails after one write execution."""

    async def __aexit__(self, *args: Any) -> None:
        self.exit_count += 1
        raise RuntimeError("mcp_session=private")


class BlockingInvokeFailingAdapter(InvokeFailingAdapter):
    """Lets a concurrent replay attempt race a failed first invocation."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def invoke_tool(
        self, tool_name: str, arguments: str | dict[str, object],
    ) -> dict[str, object]:
        self.invoke_count += 1
        self.started.set()
        await self.release.wait()
        raise RuntimeError("internal write failure")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


def _make_service(
    *,
    confirmation: Any = None,
    adapter: FakeMCPToolAdapter | None = None,
) -> tuple[Any, FakeDeepSeekClient, FakeMCPToolAdapter]:
    """Create an AIChatService with fakes for confirm_action testing."""
    from app.services.ai_chat_service import AIChatService
    from app.services.ai_action_confirmation import AIActionConfirmation

    deepseek = FakeDeepSeekClient(responses=[])
    fak = adapter or FakeMCPToolAdapter()
    if confirmation is None:
        confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    svc = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: fak,
        action_confirmation=confirmation,
        action_id_factory=lambda: "test-id",
    )
    return svc, deepseek, fak


# ===================================================================
# 1. Successful execution — add_student
# ===================================================================


def test_confirm_add_student_success() -> None:
    """Valid token executes add_student and returns success."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    result = _run_async(run())
    assert result["success"] is True
    assert "新增" in result.get("reply", "")


def test_confirm_add_student_invoke_tool_once() -> None:
    """invoke_tool must be called exactly once."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.invoke_count == 1
    assert fak.called_tools[0] == "add_student"


def test_confirm_add_student_arguments_from_token() -> None:
    """Arguments passed to invoke_tool must match token payload."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.called_args[0] == WRITE_PAYLOAD["arguments"]


def test_confirm_update_student_success() -> None:
    """Valid token for update_student executes successfully."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, UPDATE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    result = _run_async(run())
    assert result["success"] is True
    assert fak.invoke_count == 1
    assert fak.called_tools[0] == "update_student"


def test_confirm_delete_student_success() -> None:
    """Valid token for delete_student executes successfully."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, DELETE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    result = _run_async(run())
    assert result["success"] is True
    assert fak.called_tools[0] == "delete_student"


# ===================================================================
# 2. Consumption and invocation counts
# ===================================================================


def test_consume_token_called_once() -> None:
    """consume_token must be called exactly once on successful confirm."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    # consume_token was already called inside confirm_action, and it succeeded
    # Verify by trying to consume again — should raise replay
    with pytest.raises(AIConfirmationReplayError):
        confirmation.consume_token(token)


def test_invoke_tool_called_exactly_once() -> None:
    """invoke_tool must be called exactly once."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.invoke_count == 1


def test_deepseek_not_called() -> None:
    """confirm_action must not call DeepSeek."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert deepseek.call_count == 0


def test_no_new_token_created() -> None:
    """confirm_action must not create a new confirmation token."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    # Use callable wrapper that counts but still produces valid tokens
    create_count = 0

    class CountingConfirmation:
        def create_token(self, payload: dict[str, object]) -> str:
            nonlocal create_count
            create_count += 1
            return confirmation.create_token(payload)

        def consume_token(self, token_str: str) -> dict[str, object]:
            return confirmation.consume_token(token_str)

        def verify_token(self, token_str: str) -> dict[str, object]:
            return confirmation.verify_token(token_str)

    svc._action_confirmation = CountingConfirmation()

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert create_count == 0


# ===================================================================
# 3. Adapter lifecycle
# ===================================================================


def test_adapter_enter_exit_once() -> None:
    """Adapter must enter and exit exactly once on success."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.enter_count == 1
    assert fak.exit_count == 1


def test_adapter_discover_called() -> None:
    """Adapter discover_tools must be called."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.discover_count == 1


# ===================================================================
# 4. Response structure
# ===================================================================


def test_response_contains_reply() -> None:
    """Response must contain deterministic Chinese reply."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    result = _run_async(run())
    assert isinstance(result.get("reply"), str)
    assert len(result["reply"]) > 0


def test_response_no_token_or_action_id() -> None:
    """Response must not contain confirmation_token, action_id, or reasoning_content."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    result = _run_async(run())
    assert "confirmation_token" not in result
    assert "action_id" not in result
    assert "reasoning_content" not in result
    # pending_action is allowed to be None (not absent)


def test_response_no_internal_fields() -> None:
    """Response must not contain internal MCP or API data."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    result = _run_async(run())
    result_str = json.dumps(result, ensure_ascii=False)
    assert "api_key" not in result_str.lower()
    assert "api_base" not in result_str.lower()
    assert "model" not in result_str.lower()
    assert "mcp_session" not in result_str.lower()
    assert "database" not in result_str.lower()
    assert "structured_content" not in result_str
    assert "parsed_text" not in result_str


# ===================================================================
# 5. Replay protection — same token twice
# ===================================================================


def test_replay_second_confirm_rejected() -> None:
    """Same token confirmed twice must reject the second."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    # First call succeeds
    result1 = _run_async(run())
    assert result1["success"] is True

    # Second call must raise replay error
    with pytest.raises(AIConfirmationReplayError) as excinfo:
        _run_async(run())
    assert excinfo.value.code == "ai_confirmation_replayed"


def test_replay_invoke_count_still_one() -> None:
    """After replay, invoke_tool must still be exactly 1."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    with pytest.raises(AIConfirmationReplayError):
        _run_async(run())

    assert fak.invoke_count == 1


def test_replay_deepseek_not_called() -> None:
    """Replay request must not call DeepSeek."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    with pytest.raises(AIConfirmationReplayError):
        _run_async(run())

    assert deepseek.call_count == 0


def test_replay_error_safe_message() -> None:
    """Replay error must not leak token, payload, or arguments."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    with pytest.raises(AIConfirmationReplayError) as excinfo:
        _run_async(run())

    msg = str(excinfo.value)
    assert "张三" not in msg
    assert "0001" not in msg
    assert SAFE_KEY not in msg
    assert token not in msg


# ===================================================================
# 6. Permission check — read-only and unknown tools
# ===================================================================


def test_read_tool_token_not_executed() -> None:
    """Read tool in signed token must raise error, not invoke MCP."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, READ_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    with pytest.raises(AIConfirmationInvalidPayloadError):
        _run_async(run())

    assert fak.invoke_count == 0


def test_unknown_tool_token_not_executed() -> None:
    """Unknown tool in signed token must not execute MCP."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, UNKNOWN_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    with pytest.raises(AIConfirmationInvalidPayloadError):
        _run_async(run())

    assert fak.invoke_count == 0


# ===================================================================
# 7. Token error boundaries
# ===================================================================


def test_tampered_token_not_executed() -> None:
    """Tampered token must raise AIConfirmationInvalidError."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)

    # Tamper the signature deterministically
    token_body, signature = token.rsplit(".", 1)
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{token_body}.{replacement}{signature[1:]}"
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(tampered)

    with pytest.raises(AIConfirmationInvalidError):
        _run_async(run())

    assert fak.invoke_count == 0


def test_expired_token_not_executed() -> None:
    """Expired token must raise AIConfirmationExpiredError."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=300)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    with patch("itsdangerous.timed.time.time", lambda: 99_999_999_999):
        async def run() -> dict[str, object]:
            return await svc.confirm_action(token)

        with pytest.raises(AIConfirmationExpiredError) as excinfo:
            _run_async(run())

        assert excinfo.value.code == "ai_confirmation_expired"

    assert fak.invoke_count == 0


def test_confirmation_not_configured_not_executed() -> None:
    """When confirmation is None, must raise AIConfirmationNotConfiguredError."""
    from app.services.ai_chat_service import AIChatService
    from app.services.ai_action_confirmation import AIActionConfirmation

    deepseek = FakeDeepSeekClient()
    fak = FakeMCPToolAdapter()

    svc = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: fak,
        action_confirmation=None,
    )

    async def run() -> dict[str, object]:
        return await svc.confirm_action("some-token")

    with pytest.raises(AIConfirmationNotConfiguredError) as excinfo:
        _run_async(run())

    assert excinfo.value.code == "ai_confirmation_not_configured"
    assert fak.invoke_count == 0


# ===================================================================
# 8. MCP failure — token remains consumed
# ===================================================================


def test_mcp_business_error_token_consumed() -> None:
    """MCP business error must not make token reusable."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation
    fak.add_invoke_result(dict(BUSINESS_ERROR_RESULT))

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    # First call — MCP returns business error
    _run_async(run())
    assert fak.invoke_count == 1

    # Second call — must be replay
    with pytest.raises(AIConfirmationReplayError):
        _run_async(run())

    assert fak.invoke_count == 1


def test_mcp_technical_error_token_consumed() -> None:
    """MCP technical error must not make token reusable."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation
    fak.add_invoke_result(dict(TECHNICAL_ERROR_RESULT))

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.invoke_count == 1

    with pytest.raises(AIConfirmationReplayError):
        _run_async(run())

    assert fak.invoke_count == 1


def test_mcp_error_adapter_exits_normally() -> None:
    """Even with MCP error, adapter must exit cleanly."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation
    fak.add_invoke_result(dict(TECHNICAL_ERROR_RESULT))

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())
    assert fak.enter_count == 1
    assert fak.exit_count == 1


def test_invoke_exception_keeps_token_consumed_and_is_safe() -> None:
    """A failed write cannot restore its token or leak internal exception text."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_errors import AIClientError

    adapter = InvokeFailingAdapter()
    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    svc, deepseek, fak = _make_service(confirmation=confirmation, adapter=adapter)
    token = _make_token(confirmation, WRITE_PAYLOAD)

    with pytest.raises(AIClientError) as excinfo:
        _run_async(svc.confirm_action(token))

    assert all(value not in str(excinfo.value) for value in ("secret-token", "张三", "traceback"))
    assert fak.invoke_count == 1
    assert deepseek.call_count == 0
    with pytest.raises(AIConfirmationReplayError) as replay:
        _run_async(svc.confirm_action(token))
    assert replay.value.code == "ai_confirmation_replayed"
    assert fak.enter_count == 1
    assert fak.discover_count == 1
    assert fak.invoke_count == 1


def test_discovery_exception_keeps_token_consumed() -> None:
    """Discovery failure after consumption must not create another MCP session."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_errors import AIClientError

    adapter = DiscoveryFailingAdapter()
    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    svc, deepseek, fak = _make_service(confirmation=confirmation, adapter=adapter)
    token = _make_token(confirmation, WRITE_PAYLOAD)

    with pytest.raises(AIClientError):
        _run_async(svc.confirm_action(token))
    assert fak.invoke_count == 0
    assert deepseek.call_count == 0
    with pytest.raises(AIConfirmationReplayError):
        _run_async(svc.confirm_action(token))
    assert fak.enter_count == 1
    assert fak.discover_count == 1


def test_adapter_exit_exception_keeps_token_consumed() -> None:
    """Exit failure after the write must not allow a second write execution."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_errors import AIClientError

    adapter = ExitFailingAdapter()
    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    svc, deepseek, fak = _make_service(confirmation=confirmation, adapter=adapter)
    token = _make_token(confirmation, WRITE_PAYLOAD)

    with pytest.raises(AIClientError):
        _run_async(svc.confirm_action(token))
    assert fak.invoke_count == 1
    assert deepseek.call_count == 0
    with pytest.raises(AIConfirmationReplayError):
        _run_async(svc.confirm_action(token))
    assert fak.enter_count == 1
    assert fak.invoke_count == 1


def test_concurrent_confirmation_failed_winner_executes_at_most_once() -> None:
    """A failed winning request still leaves the concurrent request as replay."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_errors import AIClientError

    async def run() -> tuple[BaseException, BaseException, BlockingInvokeFailingAdapter]:
        adapter = BlockingInvokeFailingAdapter()
        confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
        svc, deepseek, fak = _make_service(confirmation=confirmation, adapter=adapter)
        token = _make_token(confirmation, WRITE_PAYLOAD)
        winner = asyncio.create_task(svc.confirm_action(token))
        await adapter.started.wait()
        try:
            await svc.confirm_action(token)
        except BaseException as replay_error:
            replay = replay_error
        else:
            raise AssertionError("concurrent confirmation unexpectedly succeeded")
        adapter.release.set()
        try:
            await winner
        except BaseException as winner_error:
            return winner_error, replay, fak
        raise AssertionError("failed write unexpectedly succeeded")

    winner_error, replay_error, adapter = _run_async(run())
    assert isinstance(winner_error, AIClientError)
    assert isinstance(replay_error, AIConfirmationReplayError)
    assert replay_error.code == "ai_confirmation_replayed"
    assert adapter.invoke_count == 1


# ===================================================================
# 9. Sequential replay
# ===================================================================


def test_sequential_replay_does_not_reach_adapter() -> None:
    """Replay request must not create adapter context."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    svc, deepseek, fak = _make_service()

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    token = _make_token(confirmation, WRITE_PAYLOAD)
    svc._action_confirmation = confirmation

    async def run() -> dict[str, object]:
        return await svc.confirm_action(token)

    _run_async(run())

    entry_count_before = fak.enter_count

    with pytest.raises(AIConfirmationReplayError):
        _run_async(run())

    assert fak.enter_count == entry_count_before


# ===================================================================
# 10. Compatibility — chat() still works
# ===================================================================


def test_chat_text_still_works() -> None:
    """chat() text Q&A must still work after confirm_action exists."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient(responses=[{"content": "你好"}])
    fak = FakeMCPToolAdapter()

    svc = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: fak,
    )

    async def run() -> dict[str, object]:
        return await svc.chat([{"role": "user", "content": "你好"}])

    result = _run_async(run())
    assert result["success"] is True


def test_chat_pending_action_still_works() -> None:
    """chat() pending action must still work after confirm_action exists."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_chat_service import AIChatService

    confirmation = AIActionConfirmation(secret_key=SAFE_KEY, token_ttl_seconds=TTL_SECONDS)
    deepseek = FakeDeepSeekClient(responses=[{
        "content": None,
        "tool_calls": [
            {"id": "cw", "type": "function", "function": {
                "name": "add_student",
                "arguments": '{"student_number": "0001", "name": "李四"}',
            }},
        ],
    }])
    fak = FakeMCPToolAdapter()

    svc = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: fak,
        action_confirmation=confirmation,
        action_id_factory=lambda: "test-id",
    )

    async def run() -> dict[str, object]:
        return await svc.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result.get("requires_confirmation") is True
    assert fak.invoke_count == 0
