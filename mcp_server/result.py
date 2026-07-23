"""Pure-Python result helpers for MCP student tools."""

from __future__ import annotations

import logging
from math import ceil
from typing import Any

from app.utils.errors import AppError

logger = logging.getLogger(__name__)


def mcp_success(
    data: Any = None,
    *,
    message: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a unified MCP success result."""
    return {
        "success": True,
        "data": data,
        "message": message,
        "error": None,
        "meta": meta or {},
    }


def mcp_error(
    *,
    message: str = "",
    code: str = "error",
    details: Any = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a unified MCP error result."""
    return {
        "success": False,
        "data": None,
        "message": message,
        "error": {
            "code": code,
            "details": details,
        },
        "meta": meta or {},
    }


def mcp_paginated(
    data: Any,
    *,
    total: int,
    page: int,
    page_size: int,
    message: str = "",
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a unified paginated MCP result."""
    if page_size <= 0:
        raise ValueError("page_size must be greater than 0")

    total_pages = ceil(total / page_size) if total else 0
    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    if extra_meta:
        for key, value in extra_meta.items():
            if key not in meta:
                meta[key] = value
    return mcp_success(data=data, message=message, meta=meta)


def mcp_result_from_exception(error: Exception) -> dict[str, Any]:
    """Translate known and unknown exceptions into unified MCP results."""
    if isinstance(error, AppError):
        return mcp_error(
            message=error.message,
            code=error.code,
            details=error.details,
        )

    logger.exception("Unhandled MCP tool failure")
    return mcp_error(
        message="Internal server error",
        code="internal_error",
        details=None,
    )
