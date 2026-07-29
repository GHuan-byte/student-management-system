"""HTTP routes for the AI chat service."""

from __future__ import annotations

import asyncio
from typing import Any

from flask import Blueprint, current_app, request
from werkzeug.exceptions import BadRequest

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


def _normalize_messages(payload: Any) -> list[dict[str, object]]:
    """Validate every browser message, then return the configured tail."""
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
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
    if "action_result" in result:
        data["action_result"] = result["action_result"]
    return data


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
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
    token = payload.get("confirmation_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("confirmation_token 无效")
    return token


@chat_bp.post("/api/chat")
def chat():
    """Validate browser messages and delegate one request to AIChatService."""
    if not request.is_json:
        return _validation_error("请求必须是 JSON")
    try:
        payload = request.get_json(silent=False)
        messages = _normalize_messages(payload)
    except (BadRequest, ValueError, TypeError):
        return _validation_error("聊天请求无效")

    service_factory = current_app.extensions["ai_chat_service_factory"]
    try:
        result = asyncio.run(service_factory().chat(messages))
    except AIClientError as error:
        return _map_ai_error(error)
    except Exception:
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )
    return api_success(data=_public_chat_data(result))


@chat_bp.post("/api/chat/actions/confirm")
def confirm_chat_action():
    """Confirm one server-signed pending write without invoking chat again."""
    if not request.is_json:
        return _validation_error("请求必须是 JSON")
    try:
        token = _confirmation_token(request.get_json(silent=False))
    except (BadRequest, ValueError, TypeError):
        return _validation_error("确认请求无效")

    service_factory = current_app.extensions["ai_chat_service_factory"]
    try:
        result = asyncio.run(service_factory().confirm_action(token))
    except AIClientError as error:
        return _map_ai_error(error)
    except Exception:
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )
    return api_success(data=_public_confirm_data(result))
