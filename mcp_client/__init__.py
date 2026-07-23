"""MCP client exports for student-management tools."""

from mcp_client.client import (
    call_mcp_tool,
    call_mcp_tool_async,
    create_server_parameters,
    list_mcp_tools,
    list_mcp_tools_async,
)

__all__ = [
    "call_mcp_tool",
    "call_mcp_tool_async",
    "create_server_parameters",
    "list_mcp_tools",
    "list_mcp_tools_async",
]
