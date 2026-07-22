"""Unified JSON response helpers."""

from __future__ import annotations

from math import ceil
from typing import Any

from flask import jsonify


def api_success(
    data: Any = None,
    message: str = "",
    meta: dict[str, Any] | None = None,
    status_code: int = 200,
):
    """Return a unified success response."""
    payload = {
        "success": True,
        "data": data,
        "message": message,
        "error": None,
        "meta": meta or {},
    }
    return jsonify(payload), status_code


def api_error(
    message: str = "",
    error: dict[str, Any] | None = None,
    status_code: int = 400,
):
    """Return a unified error response."""
    error_payload = error or {"code": "error", "details": None}
    payload = {
        "success": False,
        "data": None,
        "message": message,
        "error": {
            "code": error_payload.get("code", "error"),
            "details": error_payload.get("details"),
        },
        "meta": {},
    }
    return jsonify(payload), status_code


def api_paginated(
    data: Any,
    total: int,
    page: int,
    page_size: int,
    message: str = "",
    status_code: int = 200,
    extra_meta: dict[str, Any] | None = None,
):
    """Return a unified paginated success response."""
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
    return api_success(data=data, message=message, meta=meta, status_code=status_code)
