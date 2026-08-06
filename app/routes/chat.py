"""HTTP routes for the AI chat service."""

from __future__ import annotations

import asyncio
from typing import Any

from flask import Blueprint, current_app, g, request
from werkzeug.exceptions import BadRequest

from app.auth import can_confirm_action, role_can_execute_ai_tool
from app.logging_config import log_security_event
from app.services.ai_action import FAILED, SUCCEEDED
from app.services.ai_action_store import (
    AIActionExpiredError,
    AIActionNotExecutableError,
    AIActionNotFoundError,
)
from app.services.ai_errors import AIClientError
from app.utils.response import api_error, api_success

chat_bp = Blueprint("chat", __name__)

_ALLOWED_BROWSER_ROLES = frozenset({"user", "assistant"})
_FORBIDDEN_ACTION_RESULT_KEYS = frozenset({
    "structured_content", "parsed_text", "raw_content", "content_blocks",
    "traceback", "exception", "exception_repr", "reasoning_content",
    "command", "argv", "cwd", "database_path", "connection", "connections",
    "session", "mcp_session", "server_url", "transport", "stdout", "stderr",
    "environment", "api_key", "authorization", "authorization_header",
})

_AI_ERROR_STATUS_CODES = {
    "ai_not_configured": 503,
    "ai_auth_error": 502,
    "ai_timeout": 504,
    "ai_rate_limited": 429,
    "ai_upstream_error": 502,
    "ai_invalid_response": 502,
    "ai_tool_round_limit": 400,
    "ai_multiple_write_actions": 400,
    "ai_confirmation_not_configured": 503,
    "ai_confirmation_invalid": 400,
    "ai_confirmation_invalid_payload": 400,
    "ai_confirmation_expired": 400,
    "ai_confirmation_replayed": 409,
    "ai_confirmation_execution_failed": 502,
}


def _validation_error(message: str):
    return api_error(
        message=message,
        error={"code": "validation_error", "details": None},
        status_code=400,
    )


def _require_json_object() -> dict[str, object]:
    """Return a parsed JSON object or raise a validation-oriented error."""
    if not request.is_json:
        raise ValueError("请求必须是 JSON")
    try:
        payload = request.get_json(silent=False)
    except BadRequest as exc:
        raise ValueError("请求必须是 JSON 对象") from exc
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
    return payload


def _run_async(coroutine: Any) -> Any:
    """Drive one service coroutine for the synchronous Flask request."""
    return asyncio.run(coroutine)


def _normalize_messages(payload: Any) -> list[dict[str, object]]:
    """Validate every browser message, then return the configured tail."""
    if "messages" not in payload:
        raise ValueError("缺少 messages")
    messages = payload["messages"]
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages 必须是非空数组")

    normalized: list[dict[str, object]] = []
    max_length = current_app.config["AI_MAX_MESSAGE_LENGTH"]
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("message 必须是对象")
        role = message.get("role")
        content = message.get("content")
        if role not in _ALLOWED_BROWSER_ROLES:
            raise ValueError("message role 无效")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("message content 无效")
        if len(content) > max_length:
            raise ValueError("message content 超过长度限制")
        normalized.append({"role": role, "content": content})

    if normalized[-1]["role"] != "user":
        raise ValueError("最后一条消息必须来自用户")

    max_history = current_app.config["AI_MAX_HISTORY_MESSAGES"]
    return normalized[-max_history:]


def _public_chat_data(result: dict[str, object]) -> dict[str, object]:
    """Project the service's browser-safe chat response into route data."""
    data: dict[str, object] = {
        "reply": result.get("reply", ""),
        "requires_confirmation": bool(result.get("requires_confirmation", False)),
        "pending_action": result.get("pending_action"),
    }
    if "confirmation_token" in result:
        data["confirmation_token"] = result["confirmation_token"]
    if "action" in result:
        data["action"] = result["action"]
    if "action_result" in result:
        data["action_result"] = result["action_result"]
    return data


def _authorize_pending_action_response(result: dict[str, object]):
    if not result.get("requires_confirmation"):
        return None
    token = result.get("confirmation_token")
    if not isinstance(token, str) or not token.strip():
        return None
    confirmation = current_app.extensions.get("ai_action_confirmation")
    current_user = getattr(g, "current_user", None)
    if confirmation is None or current_user is None:
        return None
    payload = confirmation.verify_token(token)
    if can_confirm_action(current_user["role"], payload.get("tool_name")):
        return None
    _log_ai_authorization_denied(
        current_user=current_user,
        tool_name=payload.get("tool_name"),
        reason="ai_pending_action_forbidden",
    )
    return api_error(
        message="Forbidden",
        error={"code": "forbidden", "details": None},
        status_code=403,
    )


def _public_confirm_data(result: dict[str, object]) -> dict[str, object]:
    """Project confirmation output without token or invocation internals."""
    return {
        "reply": result.get("reply", ""),
        "requires_confirmation": False,
        "pending_action": None,
        "action_result": _sanitize_action_result(result.get("action_result")),
    }


def _sanitize_action_result(value: Any) -> Any:
    """Keep business data while removing nested MCP diagnostics."""
    if isinstance(value, dict):
        return {
            key: _sanitize_action_result(item)
            for key, item in value.items()
            if not isinstance(key, str) or key.lower() not in _FORBIDDEN_ACTION_RESULT_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_action_result(item) for item in value]
    return value


def _map_ai_error(error: AIClientError):
    """Map stable service errors to safe, unified HTTP JSON responses."""
    return api_error(
        message=error.safe_message,
        error={"code": error.code, "details": None},
        status_code=_AI_ERROR_STATUS_CODES.get(error.code, 500),
    )


def _confirmation_token(payload: Any) -> str:
    """Extract the sole browser-controlled field accepted by confirm."""
    token = payload.get("confirmation_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("confirmation_token 无效")
    return token


def _authorize_confirmation_token(token: str):
    confirmation = current_app.extensions.get("ai_action_confirmation")
    current_user = getattr(g, "current_user", None)
    if confirmation is None or current_user is None:
        return None
    payload = confirmation.verify_token(token)
    if role_can_execute_ai_tool(current_user["role"], payload.get("tool_name")):
        return None
    _log_ai_authorization_denied(
        current_user=current_user,
        tool_name=payload.get("tool_name"),
        reason="ai_confirmation_forbidden",
    )
    return api_error(
        message="Forbidden",
        error={"code": "forbidden", "details": None},
        status_code=403,
    )


def _log_ai_authorization_denied(*, current_user: dict[str, Any], tool_name: Any, reason: str) -> None:
    log_security_event(
        "authorization_denied",
        metadata={
            "user_id": current_user["id"],
            "username": current_user["username"],
            "role": current_user["role"],
            "endpoint": request.endpoint,
            "method": request.method,
            "tool_name": tool_name if isinstance(tool_name, str) else "unknown",
            "outcome": "denied",
            "reason": reason,
        },
    )


@chat_bp.post("/api/chat")
def chat():
    """Validate browser messages and delegate one request to AIChatService."""
    try:
        messages = _normalize_messages(_require_json_object())
    except (BadRequest, ValueError, TypeError):
        return _validation_error("聊天请求无效")

    service_factory = current_app.extensions["ai_chat_service_factory"]
    try:
        result = _run_async(service_factory().chat(messages, user_id=_current_user_id()))
    except AIClientError as error:
        return _map_ai_error(error)
    except Exception:
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )
    try:
        forbidden = _authorize_pending_action_response(result)
    except AIClientError as error:
        return _map_ai_error(error)
    if forbidden is not None:
        return forbidden
    return api_success(data=_public_chat_data(result))


@chat_bp.post("/api/chat/actions/confirm")
def confirm_chat_action():
    """Confirm one server-signed pending write without invoking chat again."""
    try:
        token = _confirmation_token(_require_json_object())
    except (BadRequest, ValueError, TypeError):
        return _validation_error("确认请求无效")
    try:
        forbidden = _authorize_confirmation_token(token)
    except AIClientError as error:
        return _map_ai_error(error)
    if forbidden is not None:
        return forbidden

    service_factory = current_app.extensions["ai_chat_service_factory"]
    try:
        result = _run_async(service_factory().confirm_action(token))
    except AIClientError as error:
        return _map_ai_error(error)
    except Exception:
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )
    return api_success(data=_public_confirm_data(result))


def _current_user_id() -> Any:
    """Return the authenticated user id or None."""
    current_user = getattr(g, "current_user", None)
    return current_user["id"] if isinstance(current_user, dict) else None


def _guided_action_store():
    """Return the in-process guided action store extension."""
    return current_app.extensions.get("ai_action_store")


def _not_found():
    return api_error(
        message="Not found",
        error={"code": "not_found", "details": None},
        status_code=404,
    )


def _result_error_code(result: dict[str, object]) -> str:
    """Extract a stable error code from a failed confirm result."""
    error = result.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return error["code"]
    action_result = result.get("action_result")
    if isinstance(action_result, dict):
        inner = action_result.get("error")
        if isinstance(inner, dict) and isinstance(inner.get("code"), str):
            return inner["code"]
    return "mcp_tool_error"


@chat_bp.get("/api/chat/actions/<uuid:action_id>")
def get_guided_action(action_id: str):
    """Return browser-safe display data for an owned guided action (no token)."""
    action_id = str(action_id)
    store = _guided_action_store()
    current_user = getattr(g, "current_user", None)
    if store is None or current_user is None:
        return _not_found()
    view = store.safe_view(action_id, current_user["id"])
    if view is None:
        # Do not reveal whether the action exists.
        return _not_found()
    response, status_code = api_success(data=view)
    response.headers["Cache-Control"] = "no-store"
    return response, status_code


@chat_bp.post("/api/chat/actions/<uuid:action_id>/confirm")
def confirm_guided_action(action_id: str):
    """Confirm a guided write by action_id using the server-held token.

    The browser never receives the confirmation token in the guided flow. The
    server consumes its own stored token and reuses the existing confirmation
    and MCP execution core (``AIChatService.confirm_action``).
    """
    action_id = str(action_id)
    store = _guided_action_store()
    current_user = getattr(g, "current_user", None)
    if store is None or current_user is None:
        return _not_found()
    action = store.get_for_user(action_id, current_user["id"])
    if action is None:
        return _not_found()
    if not role_can_execute_ai_tool(current_user["role"], action.get("tool_name")):
        _log_ai_authorization_denied(
            current_user=current_user,
            tool_name=action.get("tool_name"),
            reason="ai_guided_confirm_forbidden",
        )
        return api_error(
            message="Forbidden",
            error={"code": "forbidden", "details": None},
            status_code=403,
        )

    try:
        token = store.begin_execution(action_id)
    except AIActionExpiredError:
        return api_error(
            message="确认请求已过期，请重新发起",
            error={"code": "ai_action_expired", "details": None},
            status_code=400,
        )
    except AIActionNotFoundError:
        return _not_found()
    except AIActionNotExecutableError:
        return api_error(
            message="该操作已执行或不可再次确认",
            error={"code": "ai_action_not_executable", "details": None},
            status_code=409,
        )

    service_factory = current_app.extensions["ai_chat_service_factory"]
    try:
        result = _run_async(service_factory().confirm_action(token))
    except AIClientError as error:
        store.mark_failed(action_id, error.code)
        return _map_ai_error(error)
    except Exception:
        store.mark_failed(action_id, "internal_error")
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )

    succeeded = result.get("success") is True
    if succeeded:
        store.mark_succeeded(action_id, _sanitize_action_result(result.get("action_result")))
        status = SUCCEEDED
    else:
        store.mark_failed(action_id, _result_error_code(result))
        status = FAILED
    return api_success(data={
        "action_id": action_id,
        "status": status,
        "reply": result.get("reply", ""),
        "action_result": result.get("action_result"),
    })


@chat_bp.post("/api/chat/actions/<uuid:action_id>/cancel")
def cancel_guided_action(action_id: str):
    """Cancel a confirmable guided action owned by the current user."""
    action_id = str(action_id)
    store = _guided_action_store()
    current_user = getattr(g, "current_user", None)
    if store is None or current_user is None:
        return _not_found()
    try:
        cancelled = store.cancel(action_id, current_user["id"])
    except AIActionNotFoundError:
        return _not_found()
    except AIActionNotExecutableError:
        return api_error(
            message="该操作已执行，无法取消",
            error={"code": "ai_action_not_cancellable", "details": None},
            status_code=409,
        )
    return api_success(data={"action_id": action_id, "cancelled": cancelled})
