"""Application-level errors for AI Chat client operations."""

from __future__ import annotations


class AIClientError(Exception):
    """Base error for AI Chat client failures.

    Subclasses define a stable ``code`` and a ``safe_message`` that can be
    shown to the user without leaking secrets.
    """

    code: str = "ai_error"
    safe_message: str = "AI 服务暂时不可用"

    def __init__(self, message: str = "") -> None:
        msg = message or self.safe_message
        super().__init__(msg)
        self.message = msg


class AITimeoutError(AIClientError):
    code = "ai_timeout"
    safe_message = "AI 请求超时，请稍后重试"


class AIUpstreamError(AIClientError):
    code = "ai_upstream_error"
    safe_message = "AI 服务连接失败，请稍后重试"
