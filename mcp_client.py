from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client


PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp").strip()


def _get_tool_input_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)

    if not isinstance(schema, dict):
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    if "required" not in schema and schema["properties"]:
        schema["required"] = []
    return schema


def _parse_tool_result(result: types.CallToolResult) -> dict[str, Any]:
    is_error = bool(getattr(result, "isError", getattr(result, "is_error", False)))

    structured_content = getattr(
        result,
        "structuredContent",
        getattr(result, "structured_content", None),
    )
    if structured_content is not None:
        return {
            "success": not is_error,
            "is_error": is_error,
            "data": structured_content,
        }

    text_parts: list[str] = []
    other_parts: list[str] = []

    for item in result.content:
        if isinstance(item, types.TextContent):
            text_parts.append(item.text)
        else:
            other_parts.append(str(item))

    combined_text = "\n".join(text_parts).strip()
    parsed_content: Any = combined_text

    if combined_text:
        try:
            parsed_content = json.loads(combined_text)
        except json.JSONDecodeError:
            parsed_content = combined_text

    return {
        "success": not is_error,
        "is_error": is_error,
        "data": parsed_content,
        "other_content": other_parts,
    }


async def check_mcp_server_async() -> dict[str, Any]:
    try:
        async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialize_result = await session.initialize()
                tools_result = await session.list_tools()
                tool_names = [tool.name for tool in tools_result.tools]
                server_info = getattr(initialize_result, "serverInfo", None)
                if server_info is None:
                    server_info = getattr(initialize_result, "server_info", None)

                return {
                    "success": True,
                    "server_url": MCP_SERVER_URL,
                    "server_name": getattr(server_info, "name", None) if server_info else None,
                    "tool_count": len(tool_names),
                    "tools": tool_names,
                    "message": "MCP server is reachable and tools were loaded successfully.",
                }
    except Exception as exc:
        return {
            "success": False,
            "server_url": MCP_SERVER_URL,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def check_mcp_server() -> dict[str, Any]:
    return asyncio.run(check_mcp_server_async())


async def list_mcp_tools_async() -> list[dict[str, Any]]:
    async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": _get_tool_input_schema(tool),
                }
                for tool in result.tools
            ]


def list_mcp_tools() -> list[dict[str, Any]]:
    return asyncio.run(list_mcp_tools_async())


async def get_openai_tools_async() -> list[dict[str, Any]]:
    mcp_tools = await list_mcp_tools_async()
    openai_tools: list[dict[str, Any]] = []

    for tool in mcp_tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
        )

    return openai_tools


def get_openai_tools() -> list[dict[str, Any]]:
    return asyncio.run(get_openai_tools_async())


async def call_mcp_tool_async(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned_tool_name = str(tool_name).strip()
    if not cleaned_tool_name:
        raise ValueError("tool_name cannot be empty")

    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be a dictionary")

    try:
        async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(cleaned_tool_name, arguments=arguments)
                parsed_result = _parse_tool_result(result)
                return {
                    "tool_name": cleaned_tool_name,
                    "arguments": arguments,
                    **parsed_result,
                }
    except Exception as exc:
        return {
            "success": False,
            "is_error": True,
            "tool_name": cleaned_tool_name,
            "arguments": arguments,
            "data": None,
            "error": str(exc),
        }


def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return asyncio.run(call_mcp_tool_async(tool_name, arguments))


def main() -> None:
    print("=" * 70)
    print("MCP Client Self Check")
    print("=" * 70)

    server_status = check_mcp_server()
    print(json.dumps(server_status, ensure_ascii=False, indent=2))

    if not server_status["success"]:
        print("Start the MCP server first with: python -m mcp_server.server")
        return

    tools = list_mcp_tools()
    print("\nRegistered MCP tools:")
    for tool in tools:
        print(f"- {tool['name']}")
        if tool["description"]:
            print(f"  {tool['description'].strip().splitlines()[0]}")

    if any(tool["name"] == "mcp_health_check" for tool in tools):
        result = call_mcp_tool("mcp_health_check", {})
        print("\nmcp_health_check result:")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
