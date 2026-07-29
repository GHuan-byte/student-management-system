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
        return api_error(
            message=error.safe_message,
            error={"code": error.code, "details": None},
            status_code=500,
        )
    except Exception:
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )
    return api_success(data=_public_chat_data(result))
