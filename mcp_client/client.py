"""stdio MCP client helpers for student-management tools."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client

DEFAULT_SERVER_ARGS = ["-m", "mcp_server.server"]
DEFAULT_READ_TIMEOUT = timedelta(seconds=30)


def create_server_parameters(
    *,
    command: str | None = None,
    args: list[str] | None = None,
    database_path: str | None = None,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> StdioServerParameters:
    """Create stdio server parameters for the current project MCP server."""
    env = os.environ.copy()
    if database_path is not None:
        env["DATABASE_PATH"] = database_path
    if env_overrides:
        env.update(env_overrides)

    return StdioServerParameters(
        command=command or sys.executable,
        args=args or list(DEFAULT_SERVER_ARGS),
        env=env,
        cwd=cwd or os.getcwd(),
    )


@asynccontextmanager
async def mcp_session(
    *,
    database_path: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> Any:
    """Open, initialize, and yield an MCP client session."""
    params = create_server_parameters(
        command=command,
        args=args,
        database_path=database_path,
        cwd=cwd,
        env_overrides=env_overrides,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def list_mcp_tools_async(
    *,
    database_path: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """List all tools exposed by the stdio MCP server."""
    tools: list[dict[str, Any]] = []
    cursor: str | None = None

    async with mcp_session(
        database_path=database_path,
        command=command,
        args=args,
        cwd=cwd,
        env_overrides=env_overrides,
    ) as session:
        while True:
            result = await session.list_tools(cursor)
            tools.extend(
                {
                    "name": tool.name,
                    "title": tool.title,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                    "output_schema": tool.outputSchema,
                }
                for tool in result.tools
            )
            cursor = result.nextCursor
            if not cursor:
                break

    return tools


def _parse_tool_content(result: types.CallToolResult) -> dict[str, Any]:
    structured_content = result.structuredContent
    content_blocks: list[dict[str, Any]] = []
    text_fragments: list[str] = []

    for content_item in result.content:
        if isinstance(content_item, types.TextContent):
            content_blocks.append({"type": "text", "text": content_item.text})
            text_fragments.append(content_item.text)
        else:
            content_blocks.append(content_item.model_dump(mode="json", by_alias=True))

    parsed_text: Any = None
    combined_text = "\n".join(fragment for fragment in text_fragments if fragment).strip()
    if combined_text:
        try:
            parsed_text = json.loads(combined_text)
        except json.JSONDecodeError:
            parsed_text = combined_text

    return {
        "structured_content": structured_content,
        "parsed_text": parsed_text,
        "content_blocks": content_blocks,
    }


def _strip_sdk_error_noise(message: str) -> str:
    """Trim transport/framework noise from SDK error text."""
    cleaned = message.strip()
    cleaned = re.sub(r"^Error executing tool [^:]+:\s*", "", cleaned)
    cleaned = re.sub(r"\n\s*For further information visit .*$", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def _normalize_sdk_error_result(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    parsed_text: Any,
    content_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize MCP SDK-level errors into the unified application result contract."""
    raw_message = parsed_text if isinstance(parsed_text, str) else "Tool execution failed"
    cleaned_message = _strip_sdk_error_noise(raw_message)
    error_code = "validation_error" if "validation error" in cleaned_message.lower() else "internal_error"
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "is_error": True,
        "result": {
            "success": False,
            "data": None,
            "message": cleaned_message,
            "error": {
                "code": error_code,
                "details": {
                    "sdk_error": cleaned_message,
                },
            },
            "meta": {},
        },
        "structured_content": None,
        "parsed_text": parsed_text,
        "content": content_blocks,
    }


async def call_mcp_tool_async(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    database_path: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call one MCP tool and normalize the returned content."""
    cleaned_tool_name = str(tool_name).strip()
    if not cleaned_tool_name:
        raise ValueError("tool_name cannot be empty")
    if arguments is not None and not isinstance(arguments, dict):
        raise TypeError("arguments must be a dictionary")

    async with mcp_session(
        database_path=database_path,
        command=command,
        args=args,
        cwd=cwd,
        env_overrides=env_overrides,
    ) as session:
        result = await session.call_tool(
            cleaned_tool_name,
            arguments=arguments or {},
            read_timeout_seconds=DEFAULT_READ_TIMEOUT,
        )

    parsed = _parse_tool_content(result)
    normalized_result = parsed["structured_content"]
    if normalized_result is None:
        normalized_result = parsed["parsed_text"]

    if result.isError and not isinstance(normalized_result, dict):
        return _normalize_sdk_error_result(
            cleaned_tool_name,
            arguments or {},
            parsed_text=parsed["parsed_text"],
            content_blocks=parsed["content_blocks"],
        )

    return {
        "tool_name": cleaned_tool_name,
        "arguments": arguments or {},
        "is_error": result.isError,
        "result": normalized_result,
        "structured_content": parsed["structured_content"],
        "parsed_text": parsed["parsed_text"],
        "content": parsed["content_blocks"],
    }


def _run_sync(coroutine: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    raise RuntimeError(
        "Synchronous MCP client wrappers cannot run inside an active event loop. "
        "Use the async MCP client API instead."
    )


def list_mcp_tools(
    *,
    database_path: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Synchronously list MCP tools."""
    return _run_sync(
        list_mcp_tools_async(
            database_path=database_path,
            command=command,
            args=args,
            cwd=cwd,
            env_overrides=env_overrides,
        )
    )


def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    database_path: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    cwd: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Synchronously call an MCP tool."""
    return _run_sync(
        call_mcp_tool_async(
            tool_name,
            arguments,
            database_path=database_path,
            command=command,
            args=args,
            cwd=cwd,
            env_overrides=env_overrides,
        )
    )
