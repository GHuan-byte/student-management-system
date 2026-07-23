"""Dependency construction for the stdio MCP server."""

from __future__ import annotations

from typing import Any

from app.services.factory import build_runtime_config, create_student_service_from_config
from app.services.student_service import StudentService


def get_server_config(
    config_name: str | None = None,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_env: bool = True,
) -> dict[str, Any]:
    """Resolve runtime config for the MCP server without Flask."""
    return build_runtime_config(
        config_name,
        config_overrides=config_overrides,
        load_env=load_env,
    )


def create_student_service(
    config_name: str | None = None,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_env: bool = True,
) -> StudentService:
    """Create a student service for MCP tool calls."""
    return create_student_service_from_config(
        config_name,
        config_overrides=config_overrides,
        load_env=load_env,
    )
