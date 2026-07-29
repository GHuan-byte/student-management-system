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


class AINotConfiguredError(AIClientError):
    """Raised when AI Chat configuration is incomplete or invalid."""
    code = "ai_not_configured"
    safe_message = "AI 服务配置不完整，请检查环境变量"


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


class AIConfirmationNotConfiguredError(AIClientError):
    """Raised when write confirmation cannot be enabled due to insecure config."""
    code = "ai_confirmation_not_configured"
    safe_message = "AI 写操作确认功能未正确配置"


class AIConfirmationExpiredError(AIClientError):
    """Raised when a confirmation token has expired."""
    code = "ai_confirmation_expired"
    safe_message = "确认请求已过期，请重新发起"


class AIConfirmationInvalidError(AIClientError):
    """Raised when a confirmation token is tampered, malformed, or invalid."""
    code = "ai_confirmation_invalid"
    safe_message = "确认请求无效，请重新发起"


class AIConfirmationInvalidPayloadError(AIClientError):
    """Raised when the confirmation token payload is invalid or contains
    forbidden fields."""
    code = "ai_confirmation_invalid_payload"
    safe_message = "确认请求数据无效"


class AIConfirmationReplayError(AIClientError):
    """Raised when a confirmation token has already been consumed."""
    code = "ai_confirmation_replayed"
    safe_message = "确认请求已被使用，请重新发起"


class AIConfirmationExecutionError(AIClientError):
    """Raised when a consumed confirmation cannot complete its MCP write."""
    code = "ai_confirmation_execution_failed"
    safe_message = "确认操作执行失败，请重新发起"


class AIToolRoundLimitError(AIClientError):
    """Raised when the tool call round count exceeds AI_MAX_TOOL_ROUNDS."""
    code = "ai_tool_round_limit"
    safe_message = "AI 工具调用轮数超过限制，请重新提问"


class AIMultipleWriteActionsError(AIClientError):
    """Raised when the model requests multiple write tools in one response."""
    code = "ai_multiple_write_actions"
    safe_message = "一次只能确认一个写操作，请分别确认"
