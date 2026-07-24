"""MCP Tool Adapter — request-level session and OpenAI-compatible tool schema."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from mcp_client.client import call_tool_in_session, list_tools_in_session

OpenAITool = dict[str, Any]
SessionFactory = Callable[[], Any]


class NotInContextError(RuntimeError):
    """Raised when an adapter method is called outside the async context."""


def _mcp_to_openai_tool(mcp_tool: dict[str, Any]) -> OpenAITool:
    """Convert one MCP tool definition to OpenAI-compatible function tool."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool["description"],
            "parameters": mcp_tool["input_schema"],
        },
    }


def _parse_arguments(arguments: str | dict[str, object]) -> dict[str, object]:
    """Parse tool arguments from JSON string or pass through dict.

    Returns:
        The parsed dict.

    Raises:
        ValueError: If the input is not a valid JSON object.
    """
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        raise ValueError("arguments must be a dict or JSON string")

    parsed = json.loads(arguments)
    if not isinstance(parsed, dict):
        raise ValueError("JSON arguments must be an object")
    return parsed


def _error_result(code: str, message: str) -> dict[str, object]:
    return {
        "success": False,
        "data": None,
        "message": message,
        "error": {"code": code, "details": None},
        "meta": {},
    }


def _sanitize_result(mcp_call_result: Any) -> dict[str, object]:
    """Extract a safe, minimal result from the raw MCP call result.

    Uses ``structuredContent`` when available (the unified V2 result
    contract), otherwise falls back to JSON-parsed ``content`` text.
    Internal fields such as ``structured_content``, ``parsed_text``,
    and raw content blocks are never returned.
    """
    structured = getattr(mcp_call_result, "structuredContent", None)
    if isinstance(structured, dict):
        return dict(structured)

    content_blocks = getattr(mcp_call_result, "content", [])
    for block in content_blocks:
        text = getattr(block, "text", None) if not isinstance(block, dict) else block.get("text")
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue

    return _error_result("mcp_tool_error", "学生数据工具返回了无法解析的结果")


class MCPToolAdapter:
    """Request-level MCP session manager and tool discovery adapter.

    Usage::

        async with MCPToolAdapter() as adapter:
            tools = await adapter.discover_tools()
            openai_tools = adapter.get_openai_tools()
            # ... tool loop uses adapter._session ...

    The session is opened on ``__aenter__`` and closed on ``__aexit__``.
    An optional ``session_factory`` allows injecting a fake session for tests.
    """

    def __init__(
        self,
        *,
        database_path: str | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._database_path = database_path
        self._session_factory = session_factory
        self._session: Any = None
        self._mcp_tools: list[dict[str, Any]] = []
        self._openai_tools: list[OpenAITool] = []

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    @staticmethod
    async def _make_session_context(
        database_path: str | None,
        session_factory: SessionFactory | None,
    ) -> tuple[Any, Any]:
        """Create an async context manager and enter it, returning
        ``(context_manager, session)``.

        *Production*: context is ``mcp_session()``.
        *Test*: context is a simple wrapper that calls ``session.close()``.
        """
        if session_factory is not None:
            result = session_factory()
            if asyncio.iscoroutine(result):
                session = await result
            else:
                session = result

            # Wrap the session in a minimal async context manager so the
            # ``__aexit__`` path is identical for test and production.
            class _SessionCM:
                def __init__(self, sess: Any) -> None:
                    self._sess = sess

                async def __aenter__(self) -> Any:
                    return self._sess

                async def __aexit__(self, *args: Any) -> None:
                    if hasattr(self._sess, "close"):
                        await self._sess.close()

            cm = _SessionCM(session)
            return cm, session

        from mcp_client.client import mcp_session

        cm = mcp_session(database_path=database_path)
        session = await cm.__aenter__()
        return cm, session

    async def __aenter__(self) -> MCPToolAdapter:
        self._cm, self._session = await self._make_session_context(
            self._database_path, self._session_factory
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if hasattr(self, "_cm") and self._cm is not None:
            await self._cm.__aexit__(*args)
        self._session = None
        self._cm = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def discover_tools(self) -> list[dict[str, Any]]:
        """Discover MCP student tools in the current session.

        Returns the raw MCP tool definitions (``name``, ``description``,
        ``input_schema``).  Also caches the converted OpenAI-compatible
        tools internally.

        Raises:
            NotInContextError: If called outside the async context manager.
        """
        if self._session is None:
            raise NotInContextError(
                "MCPToolAdapter must be used inside an 'async with' context"
            )

        self._mcp_tools = await list_tools_in_session(self._session)
        self._openai_tools = [_mcp_to_openai_tool(t) for t in self._mcp_tools]
        return list(self._mcp_tools)

    def get_openai_tools(self) -> list[OpenAITool]:
        """Return the cached OpenAI-compatible tool schemas.

        Must be called after ``discover_tools()``.
        """
        return list(self._openai_tools)

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: str | dict[str, object],
    ) -> dict[str, object]:
        """Invoke a discovered MCP tool using the current session.

        Args:
            tool_name: Must be in ``allowed_tool_names``.
            arguments: Either a JSON string (parsed to dict) or a dict.

        Returns:
            A sanitized result dict with ``success``, ``data``/``error``.
        """
        if self._session is None:
            return _error_result("mcp_tool_error", "工具适配器未处于活动状态")

        if tool_name not in self.allowed_tool_names:
            return _error_result("unknown_tool", "请求的工具不可用")

        try:
            parsed_args = _parse_arguments(arguments)
        except (json.JSONDecodeError, ValueError):
            return _error_result("invalid_tool_arguments", "工具参数格式无效")

        try:
            raw_result = await call_tool_in_session(
                self._session,
                tool_name,
                parsed_args,
            )
        except Exception:
            return _error_result("mcp_tool_error", "学生数据工具暂时不可用")

        sanitized = _sanitize_result(raw_result)
        return sanitized

    @property
    def allowed_tool_names(self) -> set[str]:
        """Set of tool names discovered in the current session."""
        return {t["name"] for t in self._mcp_tools}
