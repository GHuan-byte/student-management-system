"""Tests for MCPToolAdapter — discovery and schema conversion."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mcp_client.client import DEFAULT_SERVER_ARGS

# ---------------------------------------------------------------------------
# Fake MCP session for test isolation (no real stdio server)
# ---------------------------------------------------------------------------

EXPECTED_10_TOOLS = {
    "list_students",
    "search_students",
    "get_student_by_id",
    "get_student_by_number",
    "count_students",
    "add_student",
    "update_student",
    "upsert_student",
    "delete_student",
    "batch_delete_students",
}

SAMPLE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_students",
        "title": "List Students",
        "description": "List students with optional keyword filtering, pagination, and safe sorting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Optional keyword filter."},
                "page": {"type": "integer", "description": "1-based page number.", "minimum": 1},
                "page_size": {"type": "integer", "description": "Page size from 1 to 50.", "minimum": 1, "maximum": 50},
                "sort_by": {"type": "string", "enum": ["student_number", "name", "gender", "age", "major", "year_level", "score"]},
                "sort_order": {"type": "string", "enum": ["asc", "desc"]},
            },
            "required": [],
        },
    },
    {
        "name": "search_students",
        "title": "Search Students",
        "description": "Search students by a required keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Required non-blank keyword.", "minLength": 1},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_student_by_id",
        "title": "Get Student by ID",
        "description": "Retrieve one student by positive integer ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "Positive student ID.", "minimum": 1},
            },
            "required": ["student_id"],
        },
    },
    {
        "name": "get_student_by_number",
        "title": "Get Student by Number",
        "description": "Retrieve one student by student_number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_number": {"type": "string", "description": "Non-blank student number.", "minLength": 1},
            },
            "required": ["student_number"],
        },
    },
    {
        "name": "count_students",
        "title": "Count Students",
        "description": "Count students in SQLite using keyword search predicate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Optional keyword filter."},
            },
            "required": [],
        },
    },
    {
        "name": "add_student",
        "title": "Add Student",
        "description": "Create one student using the approved student field contract.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_number": {"type": "string", "minLength": 1},
                "name": {"type": "string", "minLength": 1},
                "gender": {"type": "string"},
                "age": {"type": "integer", "minimum": 10, "maximum": 100},
                "major": {"type": "string"},
                "year_level": {"type": "string", "enum": ["大一", "大二", "大三", "大四"]},
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "phone": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["student_number", "name"],
        },
    },
    {
        "name": "update_student",
        "title": "Update Student",
        "description": "Update one student by ID using one or more editable fields.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "minimum": 1},
                "name": {"type": "string"},
                "year_level": {"type": "string", "enum": ["大一", "大二", "大三", "大四"]},
            },
            "required": ["student_id"],
        },
    },
    {
        "name": "upsert_student",
        "title": "Upsert Student",
        "description": "Create a student or update when student_number exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_number": {"type": "string", "minLength": 1},
                "name": {"type": "string", "minLength": 1},
                "year_level": {"type": "string", "enum": ["大一", "大二", "大三", "大四"]},
            },
            "required": ["student_number", "name"],
        },
    },
    {
        "name": "delete_student",
        "title": "Delete Student",
        "description": "Delete one student by positive integer ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "minimum": 1},
            },
            "required": ["student_id"],
        },
    },
    {
        "name": "batch_delete_students",
        "title": "Batch Delete Students",
        "description": "Delete multiple students in one request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_ids": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1},
                    "minItems": 1,
                    "maxItems": 50,
                },
            },
            "required": ["student_ids"],
        },
    },
]


class FakeListToolsResult:
    """Mimics ``mcp.types.ListToolsResult`` for testing."""

    def __init__(self, tools: list[Any]) -> None:
        self.tools = tools
        self.nextCursor: str | None = None


class FakeTool:
    """Mimics an MCP tool object for testing."""

    def __init__(self, name: str, title: str, description: str, inputSchema: dict[str, Any]) -> None:
        self.name = name
        self.title = title
        self.description = description
        self.inputSchema = inputSchema


def _build_fake_tools() -> list[FakeTool]:
    return [
        FakeTool(
            name=t["name"],
            title=t["title"],
            description=t["description"],
            inputSchema=t["input_schema"],
        )
        for t in SAMPLE_TOOLS
    ]


_DEFAULT_CALL_RESULT = {"success": True, "data": {"id": 1}, "message": "", "error": None, "meta": {}}


class FakeCallToolResult:
    """Mimics the return of ``session.call_tool()`` for testing."""

    def __init__(
        self,
        content: list[dict[str, Any]] | None = None,
        isError: bool = False,
        structuredContent: Any = None,
    ) -> None:
        self.content = content or [{"type": "text", "text": '{"success":true,"data":{},"message":"","error":null,"meta":{}}'}]
        self.isError = isError
        self.structuredContent = structuredContent


class FakeMCPSession:
    """In-memory fake that mimics ``mcp.ClientSession``."""

    def __init__(self, tools: list[FakeTool] | None = None) -> None:
        self._tools = tools or _build_fake_tools()
        self.call_count = 0
        self.called_tools: list[str] = []
        self.called_args: list[dict[str, Any]] = []
        self._results: list[FakeCallToolResult] = []

    def add_result(self, result: FakeCallToolResult) -> None:
        self._results.append(result)

    async def list_tools(self, cursor: str | None = None) -> FakeListToolsResult:
        return FakeListToolsResult(self._tools)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        read_timeout_seconds: Any = None,
    ) -> FakeCallToolResult:
        self.call_count += 1
        self.called_tools.append(tool_name)
        self.called_args.append(arguments or {})
        if self._results:
            return self._results.pop(0)
        return FakeCallToolResult()


class FakeAsyncContextManager:
    """Async context manager that wraps a FakeMCPSession.

    Records enter/exit counts and propagates exception info.
    """

    def __init__(self, session: FakeMCPSession | None = None) -> None:
        self._session = session or FakeMCPSession()
        self.enter_count = 0
        self.exit_count = 0
        self.received_exc_type: type[BaseException] | None = None

    async def __aenter__(self) -> FakeMCPSession:
        self.enter_count += 1
        return self._session

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.exit_count += 1
        self.received_exc_type = exc_type


def _fake_session_factory() -> FakeAsyncContextManager:
    """Factory that returns a FakeAsyncContextManager."""
    return FakeAsyncContextManager()


def _run_async(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_adapter_enters_context_and_creates_session_once() -> None:
    """Entering the adapter context must create exactly one session."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    cm = FakeAsyncContextManager()

    def factory() -> FakeAsyncContextManager:
        return cm

    async def run() -> None:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            assert adapter._session is not None

    _run_async(run())
    assert cm.enter_count == 1


def test_factory_returns_async_context_manager() -> None:
    """Factory must return an async context manager, not a bare session."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    cm = FakeAsyncContextManager()

    def factory() -> FakeAsyncContextManager:
        return cm

    async def run() -> None:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            assert adapter._session is not None

    _run_async(run())
    assert cm.enter_count == 1, "__aenter__ should be called exactly once"
    assert cm.exit_count == 1, "__aexit__ should be called exactly once"


def test_discover_returns_10_tools() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> list[dict[str, Any]]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            return await adapter.discover_tools()

    tools = _run_async(run())
    assert len(tools) == 10


def test_discovered_tool_names_are_correct() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> set[str]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            tools = await adapter.discover_tools()
            return {t["name"] for t in tools}

    names = _run_async(run())
    assert names == EXPECTED_10_TOOLS


def test_no_duplicate_tool_names() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> None:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            tools = await adapter.discover_tools()
            names = [t["name"] for t in tools]
            assert len(names) == len(set(names)), "Duplicate tool names found"

    _run_async(run())


def test_get_openai_tools_returns_converted_schema() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> list[dict[str, Any]]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()
            return adapter.get_openai_tools()

    openai_tools = _run_async(run())
    assert len(openai_tools) == 10

    count_students = next(t for t in openai_tools if t["function"]["name"] == "count_students")
    assert count_students["type"] == "function"
    assert "description" in count_students["function"]
    assert "parameters" in count_students["function"]


def test_converted_tool_preserves_description() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> str:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()
            tools = adapter.get_openai_tools()
            add = next(t for t in tools if t["function"]["name"] == "add_student")
            return add["function"]["description"]

    desc = _run_async(run())
    assert "Create one student" in desc or "create" in desc.lower()


def test_converted_tool_preserves_input_schema() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()
            tools = adapter.get_openai_tools()
            add = next(t for t in tools if t["function"]["name"] == "add_student")
            return add["function"]["parameters"]

    params = _run_async(run())
    assert params["type"] == "object"
    assert "student_number" in params["properties"]
    assert params["properties"]["student_number"]["type"] == "string"


def test_converted_tool_preserves_required() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> list[str]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()
            tools = adapter.get_openai_tools()
            add = next(t for t in tools if t["function"]["name"] == "add_student")
            return add["function"]["parameters"]["required"]

    required = _run_async(run())
    assert "student_number" in required
    assert "name" in required


def test_converted_tool_preserves_enum() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> list[str]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()
            tools = adapter.get_openai_tools()
            add = next(t for t in tools if t["function"]["name"] == "add_student")
            return add["function"]["parameters"]["properties"]["year_level"]["enum"]

    enum_vals = _run_async(run())
    assert set(enum_vals) == {"大一", "大二", "大三", "大四"}


def test_converted_tool_preserves_items_minimum() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()
            tools = adapter.get_openai_tools()
            batch = next(t for t in tools if t["function"]["name"] == "batch_delete_students")
            return batch["function"]["parameters"]["properties"]["student_ids"]

    prop = _run_async(run())
    assert prop["type"] == "array"
    assert prop["items"]["type"] == "integer"
    assert prop["items"]["minimum"] == 1
    assert prop["minItems"] == 1
    assert prop["maxItems"] == 50


def test_convert_does_not_mutate_original() -> None:
    """Conversion must not modify the original MCP tool definitions."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> None:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            original = await adapter.discover_tools()
            original_copy = [dict(t) for t in original]
            adapter.get_openai_tools()
            assert adapter._mcp_tools == original_copy, "Original tools were mutated"

    _run_async(run())


def test_discover_outside_context_raises_error() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    adapter = MCPToolAdapter(session_factory=_fake_session_factory)

    async def run() -> None:
        await adapter.discover_tools()

    with pytest.raises(RuntimeError):
        _run_async(run())


def test_exit_clears_session_and_context_refs() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    cm = FakeAsyncContextManager()

    def factory() -> FakeAsyncContextManager:
        return cm

    async def run() -> tuple:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
        return (adapter._session, adapter._session_context)

    session_ref, ctx_ref = _run_async(run())
    assert session_ref is None, "_session must be None after exit"
    assert ctx_ref is None, "_session_context must be None after exit"


def test_exit_propagates_exception_to_context() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    cm = FakeAsyncContextManager()

    def factory() -> FakeAsyncContextManager:
        return cm

    async def run() -> None:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            raise ValueError("test error")

    with pytest.raises(ValueError):
        _run_async(run())

    assert cm.exit_count == 1
    assert cm.received_exc_type is ValueError, "Exception type must propagate to __aexit__"


def test_adapter_does_not_access_real_mcp_server() -> None:
    """No real stdio MCP server should be started — fake session only."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    async def run() -> None:
        async with MCPToolAdapter(session_factory=_fake_session_factory) as adapter:
            await adapter.discover_tools()

    _run_async(run())


# ---------------------------------------------------------------------------
# invoke_tool tests
# ---------------------------------------------------------------------------


def test_invoke_known_tool_calls_session() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("count_students", {})

    result = _run_async(run())
    assert session.call_count == 1
    assert session.called_tools[0] == "count_students"


def test_invoke_with_json_string_arguments() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("count_students", '{"keyword": "test"}')

    _run_async(run())
    assert session.called_args[0] == {"keyword": "test"}


def test_invoke_with_dict_arguments() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            args = {"student_number": "00001"}
            return await adapter.invoke_tool("get_student_by_number", args)

    _run_async(run())
    assert session.called_args[0] == {"student_number": "00001"}


def test_invoke_empty_json_object_valid() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("count_students", "{}")

    result = _run_async(run())
    assert session.call_count == 1


def test_invoke_invalid_json_returns_error() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("add_student", "{not-json}")

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "invalid_tool_arguments"
    assert session.call_count == 0


def test_invoke_json_array_returns_error() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("add_student", "[1, 2, 3]")

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "invalid_tool_arguments"
    assert session.call_count == 0


def test_invoke_json_null_returns_error() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("add_student", "null")

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "invalid_tool_arguments"


def test_unknown_tool_returns_error() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("nonexistent_tool", {})

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "unknown_tool"
    assert session.call_count == 0


def test_multiple_invoke_share_same_session() -> None:
    """Multiple invoke_tool calls must reuse the same session, not call factory again."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> None:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            await adapter.invoke_tool("count_students", {})
            await adapter.invoke_tool("list_students", {})

    _run_async(run())
    assert session.call_count == 2
    assert session.called_tools == ["count_students", "list_students"]


def test_mcp_success_result_is_sanitized() -> None:
    """Success result must not contain raw MCP internals."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("count_students", {})

    result = _run_async(run())
    assert result["success"] is True
    assert "structured_content" not in result
    assert "parsed_text" not in result
    assert "content" not in result


def test_mcp_business_error_returns_tool_result() -> None:
    """MCP tool returning a business error must not throw an exception."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    session = FakeMCPSession()
    session.add_result(FakeCallToolResult(
        content=[{"type": "text", "text": '{"success":false,"data":null,"message":"Student not found","error":{"code":"not_found","details":null},"meta":{}}'}],
        isError=True,
    ))

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("get_student_by_id", {"student_id": 999})

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "not_found"


def test_mcp_technical_exception_returns_safe_error() -> None:
    """If MCP call raises, adapter must return a safe structured error."""
    from app.services.mcp_tool_adapter import MCPToolAdapter

    class BrokenSession(FakeMCPSession):
        async def call_tool(self, tool_name, arguments=None, read_timeout_seconds=None):
            raise RuntimeError("internal failure")

    session = BrokenSession()

    def factory() -> FakeAsyncContextManager:
        return FakeAsyncContextManager(session)

    async def run() -> dict[str, Any]:
        async with MCPToolAdapter(session_factory=factory) as adapter:
            await adapter.discover_tools()
            return await adapter.invoke_tool("count_students", {})

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "mcp_tool_error"


def test_invoke_outside_context_returns_error() -> None:
    from app.services.mcp_tool_adapter import MCPToolAdapter

    adapter = MCPToolAdapter(session_factory=_fake_session_factory)

    async def run() -> dict[str, Any]:
        return await adapter.invoke_tool("count_students", {})

    result = _run_async(run())
    assert result["success"] is False
    assert result["error"]["code"] == "mcp_tool_error"
