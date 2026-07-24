"""Tests for AIChatService — basic Q&A and single read-only tool call.

RED phase — AIChatService does not exist yet.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.services.ai_errors import AIWriteConfirmationRequiredError

# ---------------------------------------------------------------------------
# Fake DeepSeekClient
# ---------------------------------------------------------------------------


class FakeDeepSeekClient:
    """Fake that returns preset responses for each call."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
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


# ---------------------------------------------------------------------------
# FakeMCPToolAdapter
# ---------------------------------------------------------------------------

PRESET_OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "count_students",
            "description": "统计学生总数",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_students",
            "description": "列出学生",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_student",
            "description": "新增学生",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_number": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["student_number", "name"],
            },
        },
    },
]

PRESET_TOOL_NAMES = {t["function"]["name"] for t in PRESET_OPENAI_TOOLS}


class FakeMCPToolAdapter:
    """Fake that implements the MCPToolAdapter public interface."""

    def __init__(self) -> None:
        self.discover_count = 0
        self.invoke_count = 0
        self.enter_count = 0
        self.exit_count = 0
        self.called_tools: list[str] = []
        self.called_args: list[Any] = []
        self._invoke_results: list[dict[str, Any]] = []
        self._preset_openai_tools = list(PRESET_OPENAI_TOOLS)

    def add_invoke_result(self, result: dict[str, Any]) -> None:
        self._invoke_results.append(result)

    async def discover_tools(self) -> list[dict[str, Any]]:
        self.discover_count += 1
        return [dict(t) for t in PRESET_OPENAI_TOOLS]

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return list(self._preset_openai_tools)

    @property
    def allowed_tool_names(self) -> set[str]:
        return PRESET_TOOL_NAMES

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
        return {"success": True, "data": {"count": 42}}

    async def __aenter__(self) -> FakeMCPToolAdapter:
        self.enter_count += 1
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.exit_count += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


TEXT_RESPONSE = {"content": "当前共有 42 名学生。"}
TOOL_CALL_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "count_students",
                "arguments": "{}",
            },
        },
    ],
    "reasoning_content": "内部推理过程",
}
FINAL_RESPONSE = {"content": "根据查询，当前共有 42 名学生。"}

READ_TOOLS = frozenset({"count_students", "list_students", "search_students",
                        "get_student_by_id", "get_student_by_number"})


# ===================================================================
# 1. Ordinary text Q&A
# ===================================================================


def test_text_reply_returns_success() -> None:
    """Ordinary text reply must return success=true."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert result["success"] is True


def test_text_reply_returns_correct_content() -> None:
    """reply must equal the DeepSeek content text."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert result["reply"] == "当前共有 42 名学生。"


def test_text_deepseek_called_once() -> None:
    """DeepSeek must be called exactly once for text Q&A."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert deepseek.call_count == 1


def test_text_no_tool_called() -> None:
    """No MCP tool must be invoked for text Q&A."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert adapter.invoke_count == 0


def test_text_discover_called_once() -> None:
    """Tool discovery must be called exactly once."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient([TEXT_RESPONSE]),
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert adapter.discover_count == 1


def test_text_adapter_enter_exit_once() -> None:
    """Adapter context must enter and exit exactly once."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient([TEXT_RESPONSE]),
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1


def test_text_result_no_reasoning_content() -> None:
    """Result must not contain reasoning_content."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert "reasoning_content" not in result


def test_text_result_no_internal_fields() -> None:
    """Result must not contain tools, session, API config."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert "tools" not in result
    assert "session" not in result
    assert "api_key" not in str(result).lower()
    assert "api_base" not in str(result).lower()
    assert "model" not in str(result).lower()


# ===================================================================
# 1b.  Tools wiring — first call receives adapter tools
# ===================================================================


def test_first_call_receives_tools_from_adapter() -> None:
    """First DeepSeek call must receive the adapter's discovered tools."""
    from app.services.ai_chat_service import AIChatService

    class ToolsCapturingFake(FakeDeepSeekClient):
        """Extended fake that captures the tools argument."""

        def __init__(self) -> None:
            super().__init__([TEXT_RESPONSE])
            self.received_tools: list[dict[str, Any]] | None = None

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.received_tools = tools
            return await super().create_chat_completion(messages)

    deepseek = ToolsCapturingFake()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())

    assert deepseek.received_tools is not None
    assert len(deepseek.received_tools) == 3


def test_first_call_tools_are_adapter_openai_tools() -> None:
    """Tools passed to DeepSeek must be exactly the adapter's OpenAI tools."""
    from app.services.ai_chat_service import AIChatService

    class ToolsCapturingFake(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([TEXT_RESPONSE])
            self.received_tools: list[dict[str, Any]] | None = None

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.received_tools = tools
            return await super().create_chat_completion(messages)

    deepseek = ToolsCapturingFake()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())

    expected_names = {t["function"]["name"] for t in PRESET_OPENAI_TOOLS}
    actual_names = {t["function"]["name"] for t in deepseek.received_tools}
    assert actual_names == expected_names


def test_tool_call_second_round_tools_is_none() -> None:
    """Second DeepSeek call (after single tool result) must pass tools=None
    since the Service only implements one round of tool execution."""
    from app.services.ai_chat_service import AIChatService

    class ToolsCapturingFake(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
            self.all_received_tools: list[list[dict[str, Any]] | None] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.all_received_tools.append(tools)
            return await super().create_chat_completion(messages)

    deepseek = ToolsCapturingFake()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())

    assert len(deepseek.all_received_tools) == 2
    # First round: tools must be passed to enable model to call them
    assert deepseek.all_received_tools[0] is not None
    # Second round: tools=None — service only executes one tool round
    assert deepseek.all_received_tools[1] is None


def test_tool_call_second_round_messages_correct() -> None:
    """Second round messages must include assistant (tool_calls + reasoning)
    and tool result."""
    from app.services.ai_chat_service import AIChatService

    class MessagesCapturingFake(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
            self.all_messages: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.all_messages.append(list(messages))
            return await super().create_chat_completion(messages)

    deepseek = MessagesCapturingFake()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())

    assert len(deepseek.all_messages) == 2
    second_msgs = deepseek.all_messages[1]

    roles = [m["role"] for m in second_msgs]
    assert "user" in roles
    assert "assistant" in roles
    assert "tool" in roles

    assistant = next(m for m in second_msgs if m["role"] == "assistant")
    assert "tool_calls" in assistant
    assert assistant.get("reasoning_content") == "内部推理过程"

    tool_msg = next(m for m in second_msgs if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_001"
    assert tool_msg["name"] == "count_students"


# ===================================================================
# 2. Single read-only tool call
# ===================================================================


def test_tool_call_executes_tool() -> None:
    """First-round tool_call must execute the corresponding read tool."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert adapter.invoke_count == 1
    assert result["success"] is True


def test_tool_call_invokes_correct_tool_name() -> None:
    """invoke_tool must receive the correct tool name."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert adapter.called_tools[0] == "count_students"


def test_tool_call_passes_raw_arguments() -> None:
    """invoke_tool must receive the original arguments string."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert adapter.called_args[0] == "{}"


def test_tool_call_deepseek_called_twice() -> None:
    """DeepSeek must be called twice: first for tool_call, second for final."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert deepseek.call_count == 2


def test_tool_call_same_adapter_context() -> None:
    """Both DeepSeek calls must use the same adapter context."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1


def test_tool_call_second_messages_include_first_assistant() -> None:
    """Second DeepSeek call messages must include the first assistant response."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    # Find the assistant message
    assistant_msgs = [m for m in second_msgs if m.get("role") == "assistant"]
    assert len(assistant_msgs) >= 1


def test_tool_call_assistant_keeps_tool_calls() -> None:
    """Assistant message must preserve tool_calls."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    assistant = next(m for m in second_msgs if m.get("role") == "assistant")
    assert "tool_calls" in assistant
    assert assistant["tool_calls"][0]["function"]["name"] == "count_students"


def test_tool_call_assistant_keeps_reasoning_content() -> None:
    """Assistant message must preserve reasoning_content."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    assistant = next(m for m in second_msgs if m.get("role") == "assistant")
    assert assistant.get("reasoning_content") == "内部推理过程"


def test_tool_call_second_includes_tool_result() -> None:
    """Second round messages must contain a role=tool message."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    tool_msgs = [m for m in second_msgs if m.get("role") == "tool"]
    assert len(tool_msgs) == 1


def test_tool_result_keeps_tool_call_id() -> None:
    """Tool result message must preserve the original tool_call_id."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    assert tool_msg["tool_call_id"] == "call_001"


def test_tool_result_keeps_tool_name() -> None:
    """Tool result message must preserve the tool name."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    assert tool_msg["name"] == "count_students"


def test_tool_result_content_is_json_string() -> None:
    """Tool result content must be a valid JSON string."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    content = tool_msg["content"]
    assert isinstance(content, str)
    parsed = json.loads(content)
    assert isinstance(parsed, dict)


def test_tool_result_json_ensure_ascii_false() -> None:
    """Tool result JSON must use ensure_ascii=False (Chinese not escaped)."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": True,
        "data": {"message": "查询成功", "count": 42},
    })

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    assert "\\u67e5" not in tool_msg["content"]  # "查" unicode escape
    assert "查询成功" in tool_msg["content"]


def test_tool_result_no_mcp_debug_fields() -> None:
    """Tool result must not contain raw MCP debug fields."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": True,
        "data": {"count": 42},
    })

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    second_msgs = deepseek.calls[1]
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    content = tool_msg["content"]
    assert "structured_content" not in content
    assert "parsed_text" not in content
    assert "content" not in content.lower() or '"content"' in content


def test_tool_call_final_reply() -> None:
    """Final reply must be the second-round DeepSeek content."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert result["reply"] == "根据查询，当前共有 42 名学生。"


def test_tool_call_final_no_reasoning_content() -> None:
    """Final result must not contain reasoning_content."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert "reasoning_content" not in result


# ===================================================================
# 3. Isolation — no real services accessed
# ===================================================================


def test_no_real_deepseek_called() -> None:
    """Default tests must not access real DeepSeek."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())
    # Assert that no real HTTP transport was involved
    assert deepseek.call_count == 1


def test_no_real_mcp_server_started() -> None:
    """Default tests must not start a real MCP server."""
    from app.services.ai_chat_service import AIChatService

    service = AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient([TEXT_RESPONSE]),
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    _run_async(run())


# ===================================================================
# 4. Write tool boundary — fail-closed
# ===================================================================


def test_write_tool_not_executed() -> None:
    """Model requesting a write tool must NOT execute it."""
    from app.services.ai_chat_service import AIChatService

    write_tool_response: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {
                "id": "call_write",
                "type": "function",
                "function": {
                    "name": "add_student",
                    "arguments": '{"student_number": "0001", "name": "张三"}',
                },
            },
        ],
    }

    deepseek = FakeDeepSeekClient([write_tool_response])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    try:
        _run_async(run())
    except AIWriteConfirmationRequiredError:
        pass

    assert adapter.invoke_count == 0


def test_write_tool_returns_controlled_error() -> None:
    """Write tool request must return a controlled error, not crash."""
    from app.services.ai_chat_service import AIChatService

    write_tool_response: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {
                "id": "call_write",
                "type": "function",
                "function": {
                    "name": "add_student",
                    "arguments": '{"student_number": "0001", "name": "张三"}',
                },
            },
        ],
    }

    deepseek = FakeDeepSeekClient([write_tool_response])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())


# ===================================================================
# 5. Multiple read-only tool calls
# ===================================================================

MULTI_TOOL_RESPONSE: dict[str, Any] = {
    "content": None,
    "reasoning_content": "多个工具推理过程",
    "tool_calls": [
        {
            "id": "call_001",
            "type": "function",
            "function": {
                "name": "count_students",
                "arguments": "{}",
            },
        },
        {
            "id": "call_002",
            "type": "function",
            "function": {
                "name": "search_students",
                "arguments": '{"keyword": "计算机"}',
            },
        },
    ],
}
MULTI_TOOL_FINAL = {"content": "共有 42 名学生，其中计算机专业 10 人。"}


def test_multi_tool_both_executed() -> None:
    """Both tool_calls must be executed via invoke_tool."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert adapter.invoke_count == 2


def test_multi_tool_order_preserved() -> None:
    """Tool execution order must match tool_calls order."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert adapter.called_tools == ["count_students", "search_students"]


def test_multi_tool_correct_names_and_args() -> None:
    """Each invoke_tool must receive the correct name and arguments."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert adapter.called_tools[0] == "count_students"
    assert adapter.called_tools[1] == "search_students"
    assert adapter.called_args[0] == "{}"
    assert adapter.called_args[1] == '{"keyword": "计算机"}'


def test_multi_tool_deepseek_called_twice() -> None:
    """DeepSeek must be called exactly twice (first + final)."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert deepseek.call_count == 2


def test_multi_tool_adapter_enter_exit_once() -> None:
    """Adapter context must enter and exit exactly once."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_multi_tool_assistant_has_all_tool_calls() -> None:
    """Second-round assistant message must contain all tool_calls."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
            self.captured: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.captured.append(list(messages))
            return await super().create_chat_completion(messages)

    deepseek = MsgCapture()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    second_msgs = deepseek.captured[1]

    assistant = next(m for m in second_msgs if m["role"] == "assistant")
    assert len(assistant["tool_calls"]) == 2
    assert assistant["tool_calls"][0]["function"]["name"] == "count_students"
    assert assistant["tool_calls"][1]["function"]["name"] == "search_students"
    assert assistant.get("reasoning_content") == "多个工具推理过程"


def test_multi_tool_two_separate_tool_results() -> None:
    """Second round must have exactly two role=tool messages."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
            self.captured: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.captured.append(list(messages))
            return await super().create_chat_completion(messages)

    deepseek = MsgCapture()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    second_msgs = deepseek.captured[1]
    tool_msgs = [m for m in second_msgs if m["role"] == "tool"]
    assert len(tool_msgs) == 2


def test_multi_tool_results_correct_ids_and_names() -> None:
    """Each tool result must carry the correct tool_call_id and name."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
            self.captured: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.captured.append(list(messages))
            return await super().create_chat_completion(messages)

    deepseek = MsgCapture()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    second_msgs = deepseek.captured[1]
    tool_msgs = [m for m in second_msgs if m["role"] == "tool"]

    assert tool_msgs[0]["tool_call_id"] == "call_001"
    assert tool_msgs[0]["name"] == "count_students"
    assert tool_msgs[1]["tool_call_id"] == "call_002"
    assert tool_msgs[1]["name"] == "search_students"


def test_multi_tool_results_order_matches_calls() -> None:
    """Tool result order must match the original tool_calls order."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
            self.captured: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.captured.append(list(messages))
            return await super().create_chat_completion(messages)

    deepseek = MsgCapture()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    second_msgs = deepseek.captured[1]
    tool_msgs = [m for m in second_msgs if m["role"] == "tool"]
    ids = [m["tool_call_id"] for m in tool_msgs]
    assert ids == ["call_001", "call_002"]


def test_multi_tool_second_round_has_no_tools() -> None:
    """Second round must pass tools=None."""
    from app.services.ai_chat_service import AIChatService

    class ToolsCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
            self.tools_list: list[Any] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.tools_list.append(tools)
            return await super().create_chat_completion(messages)

    deepseek = ToolsCapture()
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert len(deepseek.tools_list) == 2
    assert deepseek.tools_list[0] is not None
    assert deepseek.tools_list[1] is None


def test_multi_tool_final_reply() -> None:
    """Final reply must be the second-round DeepSeek content."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    result = _run_async(run())
    assert result["reply"] == "共有 42 名学生，其中计算机专业 10 人。"
    assert "reasoning_content" not in result


def test_multi_tool_first_error_second_still_executes() -> None:
    """If first tool returns a business error, the second must still execute."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "not_found", "details": None},
    })
    adapter.add_invoke_result({
        "success": True,
        "data": {"count": 10},
    })

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert adapter.invoke_count == 2
    assert adapter.called_tools == ["count_students", "search_students"]


def test_multi_tool_first_mcp_error_second_still_executes() -> None:
    """If first tool returns mcp_tool_error, the second must still execute."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "mcp_tool_error", "details": None},
    })
    adapter.add_invoke_result({
        "success": True,
        "data": {"count": 10},
    })

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())
    assert adapter.invoke_count == 2
    assert adapter.called_tools == ["count_students", "search_students"]


def test_multi_tool_single_tool_still_works() -> None:
    """Existing single tool call tests must not regress."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TOOL_CALL_RESPONSE, FINAL_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert adapter.invoke_count == 1
    assert result["reply"] == "根据查询，当前共有 42 名学生。"


def test_multi_tool_no_real_services() -> None:
    """No real DeepSeek, MCP, or database access."""
    from app.services.ai_chat_service import AIChatService

    service = AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient(
            [MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL],
        ),
        mcp_adapter_factory=FakeMCPToolAdapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    _run_async(run())


# ===================================================================
# 6. Mixed read + write — fail-closed (no partial execution)
# ===================================================================

READ_FIRST_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "call_read", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
        {"id": "call_write", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0001", "name": "张三"}'
        }},
    ],
}

WRITE_FIRST_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "call_write", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0001", "name": "张三"}'
        }},
        {"id": "call_read", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
    ],
}

MULTI_WRITE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "call_w1", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0001", "name": "张三"}'
        }},
        {"id": "call_w2", "type": "function", "function": {
            "name": "delete_student", "arguments": '{"student_id": 42}'}},
    ],
}


def test_mixed_read_then_write_no_partial_execution() -> None:
    """read → write: no tool must be executed (no partial execution)."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    deepseek = FakeDeepSeekClient([READ_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())

    assert adapter.invoke_count == 0, "No tool should be executed"


def test_mixed_write_then_read_no_execution() -> None:
    """write → read: no tool must be executed."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    deepseek = FakeDeepSeekClient([WRITE_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_mixed_multiple_reads_one_write_no_execution() -> None:
    """Multiple reads + one write: no tool must be executed."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    multi_read_then_write: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "count_students", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {
                "name": "search_students", "arguments": '{"keyword": "计算机"}'}},
            {"id": "c3", "type": "function", "function": {
                "name": "add_student", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([multi_read_then_write])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_mixed_multiple_writes_no_execution() -> None:
    """Multiple write tools: no tool must be executed."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    deepseek = FakeDeepSeekClient([MULTI_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_mixed_deepseek_called_once() -> None:
    """When write tools detected, DeepSeek must be called only once."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    deepseek = FakeDeepSeekClient([READ_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())

    assert deepseek.call_count == 1


def test_mixed_adapter_still_enters_and_exits() -> None:
    """Adapter context must still enter and exit normally on mixed write."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    deepseek = FakeDeepSeekClient([READ_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError):
        _run_async(run())

    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_mixed_error_message_safe() -> None:
    """Error message must not contain tool arguments, student data, or API Key."""
    from app.services.ai_chat_service import AIChatService, AIWriteConfirmationRequiredError

    deepseek = FakeDeepSeekClient([READ_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIWriteConfirmationRequiredError) as excinfo:
        _run_async(run())

    msg = str(excinfo.value)
    assert "张三" not in msg
    assert "0001" not in msg
    assert excinfo.value.code == "ai_write_confirmation_required"


def test_mixed_all_read_still_works() -> None:
    """Pure read scenarios must still work after mixed write changes."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([MULTI_TOOL_RESPONSE, MULTI_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "统计学生"}])

    result = _run_async(run())
    assert result["success"] is True
    assert result["reply"] == "共有 42 名学生，其中计算机专业 10 人。"
