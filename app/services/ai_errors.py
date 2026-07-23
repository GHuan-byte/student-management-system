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


class AIAuthError(AIClientError):
    code = "ai_auth_error"
    safe_message = "AI 服务认证失败，请检查服务配置"


class AIRateLimitedError(AIClientError):
    code = "ai_rate_limited"
    safe_message = "AI 服务请求过于频繁，请稍后重试"


class AIInvalidResponseError(AIClientError):
    code = "ai_invalid_response"
    safe_message = "AI 服务返回了无法处理的响应"


class AIUpstreamError(AIClientError):
    code = "ai_upstream_error"
    safe_message = "AI 服务连接失败，请稍后重试"
