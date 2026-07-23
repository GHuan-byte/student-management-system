"""stdio MCP server entry point for student-management tools."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from mcp_server.dependencies import create_student_service
from mcp_server.student_tools import register_student_tools

SERVER_NAME = "Student Management MCP Server"
SERVER_INSTRUCTIONS = (
    "Use these tools to manage student records through the approved V2 service "
    "layer. Student tools reuse the same validation and database rules as the "
    "Flask REST API."
)


def configure_server_logging() -> None:
    """Configure stderr logging for MCP server startup and tool operations."""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    configure_server_logging()
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        log_level="INFO",
    )
    register_student_tools(server, service_factory=lambda: create_student_service(load_env=True))
    return server


def main() -> None:
    """Start the MCP server over stdio."""
    logging.getLogger(__name__).info("Starting MCP server in stdio mode")
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
