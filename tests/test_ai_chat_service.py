"""Tests for AIChatService — basic Q&A and single read-only tool call.

RED phase — AIChatService does not exist yet.
"""

from __future__ import annotations

import asyncio
import copy
import json
from typing import Any

import pytest

from app.services.ai_errors import AIMultipleWriteActionsError

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


class FakeAIActionConfirmation:
    """Fake that records create_token calls and returns a preset token."""

    def __init__(self, token: str = "signed-token-abc") -> None:
        self.token = token
        self.create_count = 0
        self.received_payloads: list[dict[str, object]] = []

    def create_token(self, payload: dict[str, object]) -> str:
        self.create_count += 1
        self.received_payloads.append(dict(payload))
        return self.token


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


def test_tool_call_second_round_still_receives_tools() -> None:
    """Second DeepSeek call (after single tool result) must still receive
    tools to support multi-round Tool Loop."""
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
    # Both rounds must receive tools for the Tool Loop
    assert deepseek.all_received_tools[0] is not None
    assert deepseek.all_received_tools[1] is not None


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


def test_tool_call_reasoning_is_internal_and_caller_messages_unchanged() -> None:
    """A tool round keeps reasoning only on its internal assistant message."""
    from app.services.ai_chat_service import AIChatService

    response = {
        "content": None,
        "reasoning_content": "round-one reasoning",
        "tool_calls": [
            {
                "id": "reasoning-call",
                "type": "function",
                "function": {"name": "count_students", "arguments": "{}"},
            }
        ],
    }
    caller_messages: list[dict[str, Any]] = [
        {"role": "user", "content": "How many students are there?"}
    ]
    original_messages = copy.deepcopy(caller_messages)
    deepseek = FakeDeepSeekClient([response, {"content": "There are 42 students."}])
    adapter = FakeMCPToolAdapter()
    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    _run_async(service.chat(caller_messages))

    assert caller_messages == original_messages
    second_round = deepseek.calls[1]
    assistant = next(message for message in second_round if message["role"] == "assistant")
    tool_result = next(message for message in second_round if message["role"] == "tool")
    assert assistant == {
        "role": "assistant",
        "content": None,
        "tool_calls": response["tool_calls"],
        "reasoning_content": "round-one reasoning",
    }
    assert "reasoning_content" not in tool_result


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
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())

    assert adapter.invoke_count == 0


def test_write_tool_returns_controlled_error() -> None:
    """Write tool request must return a pending action, not crash."""
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
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True


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


def test_multi_tool_second_round_receives_tools() -> None:
    """Second round must still receive tools (Tool Loop)."""
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
    assert deepseek.tools_list[1] is not None


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
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([READ_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True

    assert adapter.invoke_count == 0, "No tool should be executed"


def test_mixed_write_then_read_no_execution() -> None:
    """write → read: no tool must be executed."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([WRITE_FIRST_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True

    assert adapter.invoke_count == 0


def test_mixed_multiple_reads_one_write_no_execution() -> None:
    """Multiple reads + one write: no tool must be executed."""
    from app.services.ai_chat_service import AIChatService

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
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True

    assert adapter.invoke_count == 0


def test_mixed_multiple_writes_no_execution() -> None:
    """Multiple write tools: no tool must be executed."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([MULTI_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError) as excinfo:
        _run_async(run())

    assert excinfo.value.code == "ai_multiple_write_actions"
    assert adapter.invoke_count == 0


def test_mixed_deepseek_called_once() -> None:
    """When write tools detected, DeepSeek must be called only once."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([MULTI_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert deepseek.call_count == 1


def test_mixed_adapter_still_enters_and_exits() -> None:
    """Adapter context must still enter and exit normally on mixed write."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([MULTI_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_mixed_error_message_safe() -> None:
    """Error message must not contain tool arguments, student data, or API Key."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([MULTI_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError) as excinfo:
        _run_async(run())

    msg = str(excinfo.value)
    assert "张三" not in msg
    assert "0001" not in msg
    assert excinfo.value.code == "ai_multiple_write_actions"


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


# ===================================================================
# 7. Multiple write tool calls — fail-closed
# ===================================================================

TWO_WRITE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0001", "name": "张三"}'
        }},
        {"id": "c2", "type": "function", "function": {
            "name": "update_student",
            "arguments": '{"student_id": 1, "name": "李四"}'
        }},
    ],
}

THREE_WRITE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "delete_student", "arguments": '{"student_id": 1}'}},
        {"id": "c3", "type": "function", "function": {
            "name": "upsert_student", "arguments": "{}"}},
    ],
}

DUPLICATE_WRITE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0001", "name": "张三"}'
        }},
        {"id": "c2", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0002", "name": "王五"}'
        }},
    ],
}

REORDERED_WRITE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "update_student", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
    ],
}


def test_multi_write_two_different_tools() -> None:
    """Two different write tools: none executed."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([TWO_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_multi_write_three_different_tools() -> None:
    """Three different write tools: none executed."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([THREE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_multi_write_same_tool_twice() -> None:
    """Same write tool repeated: none executed."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([DUPLICATE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_multi_write_reordered() -> None:
    """Write tools in different order: still rejected."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([REORDERED_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.invoke_count == 0


def test_multi_write_deepseek_called_once() -> None:
    """DeepSeek called only once when multiple writes detected."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([TWO_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert deepseek.call_count == 1


def test_multi_write_adapter_lifecycle() -> None:
    """Adapter context enters and exits normally."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([TWO_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_multi_write_error_message_safe() -> None:
    """Error message must not leak sensitive data."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    deepseek = FakeDeepSeekClient([TWO_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError) as excinfo:
        _run_async(run())

    msg = str(excinfo.value)
    assert "张三" not in msg
    assert "0001" not in msg
    assert excinfo.value.code == "ai_multiple_write_actions"


def test_multi_write_single_write_still_works() -> None:
    """Single write tool must still be rejected after multi-write changes."""
    from app.services.ai_chat_service import AIChatService

    single_write: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "delete_student", "arguments": '{"student_id": 42}'}},
        ],
    }

    deepseek = FakeDeepSeekClient([single_write])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "删除学生"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True

    assert adapter.invoke_count == 0


# ===================================================================
# 8. Unknown tool — safe structured result
# ===================================================================

UNKNOWN_TOOL_RESPONSE: dict[str, Any] = {
    "content": None,
    "reasoning_content": "推理过程",
    "tool_calls": [
        {"id": "call_uk", "type": "function", "function": {
            "name": "drop_database",
            "arguments": "{}"}},
    ],
}
UNKNOWN_TOOL_FINAL = {"content": "抱歉，我无法执行该操作。"}

UNKNOWN_MIXED_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "drop_database", "arguments": "{}"}},
        {"id": "c3", "type": "function", "function": {
            "name": "list_students", "arguments": '{"page": 1}'}},
    ],
}
UNKNOWN_MIXED_FINAL = {"content": "已完成查询。"}


def test_unknown_tool_does_not_crash() -> None:
    """Unknown tool must not crash the service."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    result = _run_async(run())
    assert result["success"] is True


def test_unknown_tool_not_invoked_on_adapter() -> None:
    """Unknown tool must NOT call adapter.invoke_tool."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    _run_async(run())
    assert adapter.invoke_count == 0


def test_unknown_tool_deepseek_called_twice() -> None:
    """DeepSeek called twice: first for tool request, second for final."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    _run_async(run())
    assert deepseek.call_count == 2


def test_unknown_tool_second_has_tool_result() -> None:
    """Second round must contain a role=tool message."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
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
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msgs = [m for m in second_msgs if m["role"] == "tool"]
    assert len(tool_msgs) == 1


def test_unknown_tool_result_correct_id() -> None:
    """Tool result must carry the original tool_call_id and name."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
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
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msg = next(m for m in second_msgs if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_uk"
    assert tool_msg["name"] == "drop_database"


def test_unknown_tool_result_content_is_valid_json() -> None:
    """Tool result content must be valid JSON with error info."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
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
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msg = next(m for m in second_msgs if m["role"] == "tool")
    content = json.loads(tool_msg["content"])
    assert content["success"] is False
    assert content["error"]["code"] == "unknown_tool"


def test_unknown_tool_result_no_sensitive_data() -> None:
    """Tool result must not leak traceback, db path, session, or API Key."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([UNKNOWN_TOOL_RESPONSE, UNKNOWN_TOOL_FINAL])
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
        return await service.chat([{"role": "user", "content": "删除数据库"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msg = next(m for m in second_msgs if m["role"] == "tool")
    content_str = tool_msg["content"]
    assert "Traceback" not in content_str
    assert "database" not in content_str.lower()
    assert "session" not in content_str.lower()


def test_unknown_mixed_read_unknown_read() -> None:
    """read + unknown + read: reads execute, unknown skipped, order preserved."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([UNKNOWN_MIXED_RESPONSE, UNKNOWN_MIXED_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())

    assert adapter.invoke_count == 2
    assert adapter.called_tools == ["count_students", "list_students"]


def test_unknown_mixed_three_results_in_order() -> None:
    """read + unknown + read produces three tool results in order."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([UNKNOWN_MIXED_RESPONSE, UNKNOWN_MIXED_FINAL])
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
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msgs = [m for m in second_msgs if m["role"] == "tool"]
    assert len(tool_msgs) == 3
    assert tool_msgs[0]["tool_call_id"] == "c1"
    assert tool_msgs[1]["tool_call_id"] == "c2"
    assert tool_msgs[1]["name"] == "drop_database"
    assert tool_msgs[2]["tool_call_id"] == "c3"


def test_unknown_at_start_does_not_block_reads() -> None:
    """Unknown tool in first position must not block subsequent tools."""
    from app.services.ai_chat_service import AIChatService

    first_pos: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "drop_database", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {
                "name": "count_students", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([first_pos, UNKNOWN_MIXED_FINAL])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.invoke_count == 1
    assert adapter.called_tools[0] == "count_students"


def test_unknown_mixed_with_write_still_rejected() -> None:
    """Unknown + write must still trigger write fail-closed."""
    from app.services.ai_chat_service import AIChatService

    unknown_then_write: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "drop_database", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {
                "name": "add_student", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([unknown_then_write])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True

    assert adapter.invoke_count == 0


# ===================================================================
# 9. Multi-round Tool Loop
# ===================================================================

ROUND1_RESPONSE: dict[str, Any] = {
    "content": None,
    "reasoning_content": "推理第一轮",
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
    ],
}

ROUND2_RESPONSE: dict[str, Any] = {
    "content": None,
    "reasoning_content": "推理第二轮",
    "tool_calls": [
        {"id": "c2", "type": "function", "function": {
            "name": "search_students",
            "arguments": '{"keyword": "计算机"}'}},
    ],
}

FINAL_TEXT = {"content": "最终回答"}

ROUND1_TWO_TOOLS: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "r1t1", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
        {"id": "r1t2", "type": "function", "function": {
            "name": "list_students", "arguments": '{"page": 1}'}},
    ],
}


def test_multi_round_three_calls_three_rounds() -> None:
    """Three DeepSeek calls across two tool rounds + final text."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert deepseek.call_count == 3
    assert result["reply"] == "最终回答"


def test_multi_round_both_tools_executed() -> None:
    """Both tool calls across rounds must be executed."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.invoke_count == 2
    assert adapter.called_tools == ["count_students", "search_students"]


def test_multi_round_adapter_once() -> None:
    """Adapter context must enter/exit/discover exactly once."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_multi_round_each_round_receives_tools() -> None:
    """Each round must receive tools (not None)."""
    from app.services.ai_chat_service import AIChatService

    class ToolsCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
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
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    # All 3 calls must receive tools
    assert all(t is not None for t in deepseek.tools_list)


def test_multi_round_messages_contain_two_assistants() -> None:
    """Messages must contain two assistant tool-call messages."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
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
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())

    third_msgs = deepseek.captured[2]
    assistant_msgs = [m for m in third_msgs if m["role"] == "assistant"]
    tool_msgs = [m for m in third_msgs if m["role"] == "tool"]
    assert len(assistant_msgs) == 2
    assert len(tool_msgs) == 2


def test_multi_round_reasoning_content_per_round() -> None:
    """Each assistant message must carry its own reasoning_content."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
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
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())

    third_msgs = deepseek.captured[2]
    assistants = [m for m in third_msgs if m["role"] == "assistant"]
    assert assistants[0].get("reasoning_content") == "推理第一轮"
    assert assistants[1].get("reasoning_content") == "推理第二轮"


def test_multi_round_final_no_reasoning() -> None:
    """Final result must not contain reasoning_content."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert "reasoning_content" not in result


# ===================================================================
# 10. Same round multi-tool + next round tool
# ===================================================================


def test_multi_round_round1_two_tools_round2_one_tool() -> None:
    """Round 1 has 2 tools, round 2 has 1 tool — all executed."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([ROUND1_TWO_TOOLS, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.invoke_count == 3
    assert adapter.called_tools == ["count_students", "list_students", "search_students"]


def test_multi_round_unknown_then_read_next_round() -> None:
    """Unknown in round 1, read in round 2 — both rounds handled."""
    from app.services.ai_chat_service import AIChatService

    unknown_round: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "drop_database", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([unknown_round, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.invoke_count == 1  # Only round 2 read tool
    assert adapter.called_tools[0] == "search_students"


# ===================================================================
# 11. Write tool in later round
# ===================================================================


def test_multi_round_write_in_round2_rejected() -> None:
    """Write tool in round 2: round 2 not executed, round 1 preserved."""
    from app.services.ai_chat_service import AIChatService

    write_round: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c2", "type": "function", "function": {
                "name": "add_student", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, write_round])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=FakeAIActionConfirmation(),
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert result["requires_confirmation"] is True

    assert adapter.invoke_count == 1
    assert adapter.called_tools[0] == "count_students"


# ===================================================================
# 12. Maximum tool rounds
# ===================================================================


def test_max_rounds_1_first_ok_second_rejected() -> None:
    """max_tool_rounds=1: first round ok, second raises limit error."""
    from app.services.ai_chat_service import (
        AIChatService,
        AIToolRoundLimitError,
    )

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        max_tool_rounds=1,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    with pytest.raises(AIToolRoundLimitError) as excinfo:
        _run_async(run())

    assert excinfo.value.code == "ai_tool_round_limit"


def test_max_rounds_1_first_tool_executed() -> None:
    """With max_tool_rounds=1, the first round's tool is still executed."""
    from app.services.ai_chat_service import AIChatService, AIToolRoundLimitError

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        max_tool_rounds=1,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    with pytest.raises(AIToolRoundLimitError):
        _run_async(run())

    assert adapter.invoke_count == 1


def test_max_rounds_2_third_rejected() -> None:
    """max_tool_rounds=2: two rounds ok, third raises limit."""
    from app.services.ai_chat_service import (
        AIChatService,
        AIToolRoundLimitError,
    )

    third_round: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c3", "type": "function", "function": {
                "name": "list_students", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, third_round])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        max_tool_rounds=2,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    with pytest.raises(AIToolRoundLimitError):
        _run_async(run())

    assert adapter.invoke_count == 2


def test_max_rounds_not_reached_with_text() -> None:
    """Normal text reply before hitting max rounds is fine."""
    from app.services.ai_chat_service import AIChatService

    deepseek = FakeDeepSeekClient([TEXT_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        max_tool_rounds=1,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "有多少学生？"}])

    result = _run_async(run())
    assert result["success"] is True


def test_max_rounds_adapter_cleaned_up() -> None:
    """After limit error, adapter context must exit cleanly."""
    from app.services.ai_chat_service import (
        AIChatService,
        AIToolRoundLimitError,
    )

    deepseek = FakeDeepSeekClient([ROUND1_RESPONSE, ROUND2_RESPONSE, FINAL_TEXT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        max_tool_rounds=1,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    with pytest.raises(AIToolRoundLimitError):
        _run_async(run())

    assert adapter.exit_count == 1


# ===================================================================
# 13. MCP error handling — safe Tool Results
# ===================================================================

ERROR_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
    ],
}
ERROR_FINAL = {"content": "查询时遇到错误，请稍后重试。"}


def test_mcp_business_error_does_not_crash() -> None:
    """Business error (not_found) must not crash the service."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "not_found", "message": "Student not found"},
    })

    deepseek = FakeDeepSeekClient([ERROR_RESPONSE, ERROR_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert result["success"] is True
    assert result["reply"] == "查询时遇到错误，请稍后重试。"


def test_mcp_technical_error_does_not_crash() -> None:
    """mcp_tool_error must not crash the service."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "mcp_tool_error", "message": "学生数据工具暂时不可用"},
    })

    deepseek = FakeDeepSeekClient([ERROR_RESPONSE, ERROR_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert result["success"] is True
    assert result["reply"] == "查询时遇到错误，请稍后重试。"


def test_mcp_business_error_then_read_still_executes() -> None:
    """Business error in first tool must not block second read tool."""
    from app.services.ai_chat_service import AIChatService

    two_tool_error: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "count_students", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {
                "name": "list_students", "arguments": '{"page": 1}'}},
        ],
    }

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "not_found", "message": "Not found"},
    })
    adapter.add_invoke_result({
        "success": True,
        "data": {"count": 10},
    })

    deepseek = FakeDeepSeekClient([two_tool_error, ERROR_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.invoke_count == 2
    assert adapter.called_tools == ["count_students", "list_students"]


def test_mcp_technical_error_then_read_still_executes() -> None:
    """mcp_tool_error in first tool must not block second read tool."""
    from app.services.ai_chat_service import AIChatService

    two_tool_error: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "count_students", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {
                "name": "search_students",
                "arguments": '{"keyword": "计算机"}'}},
        ],
    }

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "mcp_tool_error", "message": "暂不可用"},
    })
    adapter.add_invoke_result({
        "success": True,
        "data": {"count": 10},
    })

    deepseek = FakeDeepSeekClient([two_tool_error, ERROR_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.invoke_count == 2


def test_mcp_error_tool_result_json_structure() -> None:
    """Tool Result JSON must preserve error.code and error.message safely."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([ERROR_RESPONSE, ERROR_FINAL])
            self.captured: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.captured.append(list(messages))
            return await super().create_chat_completion(messages)

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "not_found", "message": "未找到"},
    })

    deepseek = MsgCapture()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msg = next(m for m in second_msgs if m["role"] == "tool")
    content = json.loads(tool_msg["content"])
    assert content["success"] is False
    assert content["error"]["code"] == "not_found"
    assert content["error"]["message"] == "未找到"
    assert "structured_content" not in tool_msg["content"]
    assert "parsed_text" not in tool_msg["content"]


def test_mcp_error_tool_result_no_debug_fields() -> None:
    """Tool Result must not contain traceback, db path, session."""
    from app.services.ai_chat_service import AIChatService

    class MsgCapture(FakeDeepSeekClient):
        def __init__(self) -> None:
            super().__init__([ERROR_RESPONSE, ERROR_FINAL])
            self.captured: list[list[dict[str, Any]]] = []

        async def create_chat_completion(
            self,
            messages: list[dict[str, str]],
            *,
            tools: list[dict[str, Any]] | None = None,
        ) -> dict[str, Any]:
            self.captured.append(list(messages))
            return await super().create_chat_completion(messages)

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "mcp_tool_error", "message": "err"},
    })

    deepseek = MsgCapture()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())

    second_msgs = deepseek.captured[1]
    tool_msg = next(m for m in second_msgs if m["role"] == "tool")
    content_str = tool_msg["content"]
    assert "Traceback" not in content_str
    assert "database" not in content_str.lower()
    assert "session" not in content_str.lower()


def test_mcp_error_multi_round_continues() -> None:
    """Error in round 1, next round must still execute."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "mcp_tool_error", "message": "err"},
    })

    deepseek = FakeDeepSeekClient([
        ERROR_RESPONSE,
        ROUND2_RESPONSE,
        FINAL_TEXT,
    ])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert adapter.invoke_count == 2
    assert result["reply"] == "最终回答"


def test_mcp_error_adapter_context_once() -> None:
    """Even with MCP errors, adapter context enters/exits once."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "mcp_tool_error", "message": "err"},
    })

    deepseek = FakeDeepSeekClient([ERROR_RESPONSE, ERROR_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    _run_async(run())
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_mcp_error_final_no_reasoning() -> None:
    """Final result must not contain reasoning_content with MCP errors."""
    from app.services.ai_chat_service import AIChatService

    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": False,
        "error": {"code": "not_found", "message": "err"},
    })

    error_with_reasoning: dict[str, Any] = {
        "content": None,
        "reasoning_content": "推理内容",
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {
                "name": "count_students", "arguments": "{}"}},
        ],
    }

    deepseek = FakeDeepSeekClient([error_with_reasoning, ERROR_FINAL])

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "查数据"}])

    result = _run_async(run())
    assert "reasoning_content" not in result


# ===================================================================
# 14. Write tool → Pending Action
# ===================================================================

SINGLE_WRITE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student",
            "arguments": '{"student_number": "0001", "name": "李四"}',
        }},
    ],
}

WRITE_UPDATE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cu", "type": "function", "function": {
            "name": "update_student", "arguments": '{"student_id": 1}'}},
    ],
}

WRITE_DELETE_RESPONSE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cd", "type": "function", "function": {
            "name": "delete_student", "arguments": '{"student_id": 42}'}},
    ],
}

READ_THEN_WRITE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cr", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
        {"id": "cw", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
    ],
}

WRITE_THEN_READ: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
        {"id": "cr", "type": "function", "function": {
            "name": "count_students", "arguments": "{}"}},
    ],
}

MULTI_READ_ONE_WRITE: dict[str, Any] = {
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

UNKNOWN_THEN_WRITE: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "drop_database", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
    ],
}

TWO_WRITES_SAME: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
    ],
}

TWO_WRITES_DIFFERENT: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "delete_student", "arguments": '{"student_id": 1}'}},
    ],
}

THREE_WRITES: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "add_student", "arguments": "{}"}},
        {"id": "c2", "type": "function", "function": {
            "name": "update_student", "arguments": "{}"}},
        {"id": "c3", "type": "function", "function": {
            "name": "delete_student", "arguments": "{}"}},
    ],
}

FAKE_TOKEN = "fake-123"
ACTION_ID = "action-001"


def test_single_write_returns_pending_action() -> None:
    """Single write tool must return a pending action structure."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation(token=FAKE_TOKEN)
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert result["success"] is True
    assert result.get("requires_confirmation") is True
    assert result.get("confirmation_token") == FAKE_TOKEN
    assert "pending_action" in result


def test_single_write_no_tool_executed() -> None:
    """Single write tool must not execute any MCP tool."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())
    assert adapter.invoke_count == 0


def test_single_write_deepseek_called_once() -> None:
    """Only one DeepSeek call when write tool detected."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())
    assert deepseek.call_count == 1


def test_single_write_create_token_called() -> None:
    """AIActionConfirmation.create_token must be called exactly once."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())
    assert confirmation.create_count == 1


def test_single_write_token_payload_has_correct_fields() -> None:
    """Token payload must contain tool_name, arguments, action_id."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())

    payload = confirmation.received_payloads[0]
    assert payload["tool_name"] == "add_student"
    assert payload["arguments"] == {"student_number": "0001", "name": "李四"}
    assert payload["action_id"] == ACTION_ID


def test_single_write_pending_action_summary() -> None:
    """Pending action must contain a summary string."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    pa = result.get("pending_action", {})
    assert isinstance(pa.get("summary"), str)
    assert len(pa["summary"]) > 0


def test_single_write_pending_action_safe_arguments() -> None:
    """Pending action must contain safe_arguments."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert "safe_arguments" in result.get("pending_action", {})


def test_pending_action_safe_arguments_exclude_forbidden_fields() -> None:
    """The browser-facing preview must not echo internal token fields."""
    from app.services.ai_chat_service import AIChatService

    write_with_internal_fields = {
        "content": None,
        "tool_calls": [
            {
                "id": "safe-preview",
                "type": "function",
                "function": {
                    "name": "add_student",
                    "arguments": json.dumps(
                        {
                            "student_number": "0001",
                            "name": "李四",
                            "api_key": "must-not-reach-browser",
                            "details": {
                                "Authorization": "must-not-reach-browser",
                                "reasoning_content": "internal reasoning",
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            }
        ],
    }
    confirmation = FakeAIActionConfirmation()
    service = AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient([write_with_internal_fields]),
        mcp_adapter_factory=FakeMCPToolAdapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    result = _run_async(service.chat([{"role": "user", "content": "新增学生"}]))

    preview = result["pending_action"]["safe_arguments"]
    assert "student_number" in preview
    assert "李四" in preview
    assert "api_key" not in preview.lower()
    assert "authorization" not in preview.lower()
    assert "reasoning_content" not in preview.lower()
    assert "must-not-reach-browser" not in preview


def test_single_write_no_reasoning_in_result() -> None:
    """Pending action result must not contain reasoning_content."""
    from app.services.ai_chat_service import AIChatService

    with_reasoning: dict[str, Any] = {
        "content": None,
        "reasoning_content": "内部推理",
        "tool_calls": [
            {"id": "cw", "type": "function", "function": {
                "name": "add_student", "arguments": "{}"}},
        ],
    }

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([with_reasoning])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert "reasoning_content" not in result


def test_confirmed_action_result_strips_raw_mcp_diagnostics() -> None:
    """Confirmed browser output must keep business data but exclude MCP internals."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_chat_service import AIChatService

    confirmation = AIActionConfirmation(
        secret_key="test-confirmation-secret",
        token_ttl_seconds=300,
    )
    adapter = FakeMCPToolAdapter()
    adapter.add_invoke_result({
        "success": True,
        "data": {
            "student": {"id": 1, "name": "张三"},
            "structured_content": {"private": "mcp payload"},
            "parsed_text": "private parser output",
            "traceback": "private traceback",
            "reasoning_content": "private reasoning",
            "session": "private session",
            "related_students": [
                {
                    "id": 2,
                    "name": "李四",
                    "Content_Blocks": "private content blocks",
                    "server_url": "private server URL",
                },
            ],
        },
    })
    service = AIChatService(
        deepseek_client_factory=lambda: FakeDeepSeekClient([]),
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
    )
    token = confirmation.create_token({
        "tool_name": "add_student",
        "arguments": {"student_number": "0001", "name": "张三"},
        "action_id": "privacy-test-action",
    })

    result = _run_async(service.confirm_action(token))

    assert result["action_result"] == {
        "success": True,
        "data": {
            "student": {"id": 1, "name": "张三"},
            "related_students": [{"id": 2, "name": "李四"}],
        },
    }
    public_output = json.dumps(result, ensure_ascii=False)
    for forbidden in (
        "structured_content", "parsed_text", "traceback", "reasoning_content", "session",
        "content_blocks", "server_url",
    ):
        assert forbidden not in public_output


def test_update_student_returns_pending_action() -> None:
    """update_student also returns pending action."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([WRITE_UPDATE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "修改学生"}])

    result = _run_async(run())
    assert result.get("requires_confirmation") is True
    assert confirmation.received_payloads[0]["tool_name"] == "update_student"


def test_delete_student_returns_pending_action() -> None:
    """delete_student also returns pending action."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([WRITE_DELETE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "删除学生"}])

    result = _run_async(run())
    assert result.get("requires_confirmation") is True


def test_adapter_lifecycle_with_pending_action() -> None:
    """Adapter enter/exit/discover each exactly once."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


# ===================================================================
# 15. Mixed read + single write — no partial execution
# ===================================================================


def test_read_then_write_no_read_execution() -> None:
    """read → write: no read tool executed, one pending action."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([READ_THEN_WRITE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert adapter.invoke_count == 0
    assert result.get("requires_confirmation") is True
    assert confirmation.create_count == 1


def test_write_then_read_no_execution() -> None:
    """write → read: no tool executed, one pending action."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([WRITE_THEN_READ])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert adapter.invoke_count == 0
    assert result.get("requires_confirmation") is True


def test_multi_read_one_write_no_execution() -> None:
    """Multiple reads + one write: no tools executed, one pending action."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([MULTI_READ_ONE_WRITE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert adapter.invoke_count == 0
    assert result.get("requires_confirmation") is True
    assert confirmation.create_count == 1


def test_unknown_then_write_generates_pending_action() -> None:
    """Unknown + one write: write confirmation takes priority."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([UNKNOWN_THEN_WRITE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    assert adapter.invoke_count == 0
    assert result.get("requires_confirmation") is True
    assert confirmation.create_count == 1


# ===================================================================
# 16. Multiple write tools → ai_multiple_write_actions
# ===================================================================


def test_two_same_writes_raises_multiple() -> None:
    """Same write tool twice: ai_multiple_write_actions."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([TWO_WRITES_SAME])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError) as excinfo:
        _run_async(run())

    assert excinfo.value.code == "ai_multiple_write_actions"
    assert adapter.invoke_count == 0
    assert confirmation.create_count == 0


def test_two_different_writes_raises_multiple() -> None:
    """Two different write tools: ai_multiple_write_actions."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([TWO_WRITES_DIFFERENT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.invoke_count == 0
    assert confirmation.create_count == 0


def test_three_writes_raises_multiple() -> None:
    """Three write tools: ai_multiple_write_actions."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([THREE_WRITES])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.invoke_count == 0
    assert confirmation.create_count == 0
    assert deepseek.call_count == 1


def test_multiple_writes_deepseek_called_once() -> None:
    """Only one DeepSeek call when multiple writes detected."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([TWO_WRITES_DIFFERENT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert deepseek.call_count == 1


def test_multiple_writes_adapter_lifecycle() -> None:
    """Adapter context exits normally after multi-write error."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([TWO_WRITES_DIFFERENT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert adapter.enter_count == 1
    assert adapter.exit_count == 1
    assert adapter.discover_count == 1


def test_multiple_writes_no_confirmation_token() -> None:
    """No confirmation token created for multiple writes."""
    from app.services.ai_chat_service import AIChatService, AIMultipleWriteActionsError

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([TWO_WRITES_DIFFERENT])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIMultipleWriteActionsError):
        _run_async(run())

    assert confirmation.create_count == 0


# ===================================================================
# 17. Configuration errors — fail-closed
# ===================================================================


def test_confirmation_not_configured_fail_closed() -> None:
    """If confirmation is absent, a write request fails before any execution."""
    from app.services.ai_chat_service import AIChatService
    from app.services.ai_errors import AIConfirmationNotConfiguredError

    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=None,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    with pytest.raises(AIConfirmationNotConfiguredError):
        _run_async(run())
    assert adapter.invoke_count == 0
    assert deepseek.call_count == 1
    assert adapter.enter_count == 1
    assert adapter.exit_count == 1


# ===================================================================
# 18. Action ID contract — must be non-empty and unique
# ===================================================================


def test_default_action_id_non_empty() -> None:
    """When action_id_factory is None, action_id must still be non-empty."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=None,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())
    assert confirmation.create_count == 1
    payload = confirmation.received_payloads[0]
    action_id = payload.get("action_id", "")
    assert isinstance(action_id, str)
    assert len(action_id) > 0, "action_id must be non-empty even without explicit factory"


def test_consecutive_pending_actions_different_ids() -> None:
    """Two pending actions (across two chat calls) must have different action_ids."""
    from app.services.ai_chat_service import AIChatService

    def make_service() -> AIChatService:
        c = FakeAIActionConfirmation()
        return AIChatService(
            deepseek_client_factory=lambda: FakeDeepSeekClient([SINGLE_WRITE_RESPONSE]),
            mcp_adapter_factory=FakeMCPToolAdapter,
            action_confirmation=c,
            action_id_factory=None,
        ), c

    async def run(service: AIChatService) -> dict[str, object]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    svc1, conf1 = make_service()
    svc2, conf2 = make_service()

    _run_async(run(svc1))
    _run_async(run(svc2))

    id1 = conf1.received_payloads[0]["action_id"]
    id2 = conf2.received_payloads[0]["action_id"]
    assert id1 != id2, "Two pending actions must have different action_ids"


def test_model_action_id_not_used_in_token() -> None:
    """Model-supplied action_id in arguments must not override server action_id."""
    from app.services.ai_chat_service import AIChatService

    model_override_response: dict[str, Any] = {
        "content": None,
        "tool_calls": [
            {"id": "cw", "type": "function", "function": {
                "name": "add_student",
                "arguments": '{"student_number": "0001", "name": "李四", "action_id": "fake-from-model"}',
            }},
        ],
    }

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([model_override_response])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: "server-generated-id",
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    _run_async(run())

    payload = confirmation.received_payloads[0]
    # Server-generated action_id must be at top level
    assert payload["action_id"] == "server-generated-id"
    # Model's "action_id" must be inside arguments, not at top level
    assert payload.get("action_id") != "fake-from-model"
    # The model-supplied action_id should be in arguments
    assert payload["arguments"].get("action_id") == "fake-from-model"


# ===================================================================
# 19. Invalid arguments — no token, safe error
# ===================================================================

INVALID_JSON_ARGS: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student",
            "arguments": "not-valid-json-at-all",
        }},
    ],
}

LIST_ARGS: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student",
            "arguments": "[1, 2, 3]",
        }},
    ],
}

NULL_ARGS: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student",
            "arguments": "null",
        }},
    ],
}

STRING_ARGS: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student",
            "arguments": '"just-a-string"',
        }},
    ],
}

NUMBER_ARGS: dict[str, Any] = {
    "content": None,
    "tool_calls": [
        {"id": "cw", "type": "function", "function": {
            "name": "add_student",
            "arguments": "42",
        }},
    ],
}


def _assert_invalid_arguments_result(result: dict[str, object]) -> None:
    """Assert that invalid arguments produce a safe error, not a token."""
    assert result.get("success") is False
    assert result.get("requires_confirmation") is not True
    assert "confirmation_token" not in result or result.get("confirmation_token") in (None, "")
    assert "pending_action" not in result


def test_invalid_json_arguments_no_token() -> None:
    """Invalid JSON arguments must not create a token."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([INVALID_JSON_ARGS])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    _assert_invalid_arguments_result(result)
    assert confirmation.create_count == 0
    assert adapter.invoke_count == 0


def test_invalid_json_safe_error_message() -> None:
    """Error message must not leak arguments, student data, or API Key."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([INVALID_JSON_ARGS])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    reply = str(result.get("reply", ""))
    assert "not-valid-json" not in reply
    assert "新增" in reply or "参数" in reply


def test_arguments_list_no_token() -> None:
    """JSON array arguments must not create a token."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([LIST_ARGS])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    _assert_invalid_arguments_result(result)
    assert confirmation.create_count == 0
    assert adapter.invoke_count == 0


def test_arguments_null_no_token() -> None:
    """JSON null arguments must not create a token."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([NULL_ARGS])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    _assert_invalid_arguments_result(result)
    assert confirmation.create_count == 0
    assert adapter.invoke_count == 0


def test_arguments_string_no_token() -> None:
    """JSON string arguments must not create a token."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([STRING_ARGS])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    _assert_invalid_arguments_result(result)
    assert confirmation.create_count == 0
    assert adapter.invoke_count == 0


def test_arguments_number_no_token() -> None:
    """JSON number arguments must not create a token."""
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([NUMBER_ARGS])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())
    _assert_invalid_arguments_result(result)
    assert confirmation.create_count == 0
    assert adapter.invoke_count == 0


# ===================================================================
# 20. Cancelled write does not execute — pending action is not auto-executed
# ===================================================================


def test_pending_action_not_auto_executed() -> None:
    """Creating a pending action must NOT auto-execute the write tool.

    Cancellation means simply not calling confirm_action. The service
    must not execute any background or delayed write after returning
    a pending action.
    """
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())

    # Pending action is returned — write tool is NOT executed
    assert result.get("requires_confirmation") is True
    assert adapter.invoke_count == 0
    assert confirmation.create_count == 1

    # The chat() method does NOT schedule background work — no side effects
    assert adapter.exit_count == 1
    assert deepseek.call_count == 1

    # Token exists but is NOT consumed
    # verify_token can still decode the token (TTL not expired)
    try:
        decoded = confirmation.verify_token(result["confirmation_token"])
        assert decoded["tool_name"] == "add_student"
    except Exception:
        pass  # FakeAIActionConfirmation may not have verify_token


def test_cancel_no_confirm_no_execution() -> None:
    """Without calling confirm_action, no MCP tool is ever executed.

    This is the core contract of cancellation — the user simply
    discards the pending action on the frontend. No server call
    is required because the service never auto-executes pending
    actions.
    """
    from app.services.ai_chat_service import AIChatService

    confirmation = FakeAIActionConfirmation()
    deepseek = FakeDeepSeekClient([SINGLE_WRITE_RESPONSE])
    adapter = FakeMCPToolAdapter()

    service = AIChatService(
        deepseek_client_factory=lambda: deepseek,
        mcp_adapter_factory=lambda: adapter,
        action_confirmation=confirmation,
        action_id_factory=lambda: ACTION_ID,
    )

    async def run() -> dict[str, Any]:
        return await service.chat([{"role": "user", "content": "新增学生"}])

    result = _run_async(run())

    # Verify the pending action was created but NOT auto-executed
    assert result.get("requires_confirmation") is True
    assert adapter.invoke_count == 0
    assert deepseek.call_count == 1
    assert confirmation.create_count == 1

    # No confirm_action was called — no consume, no write tool execution
    # Token remains unconsumed (naturally expires via TTL)

    # Confirm that database/MCP was not affected:
    assert adapter.discover_count == 1
    assert adapter.exit_count == 1
