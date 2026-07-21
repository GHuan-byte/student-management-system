"""Global error handler registration."""

from __future__ import annotations

import logging

from flask import Flask
from werkzeug.exceptions import HTTPException

from app.utils.errors import AppError
from app.utils.response import api_error


def register_error_handlers(app: Flask) -> None:
    """Register global error handlers."""

    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return api_error(
            message=error.message,
            error={"code": error.code, "details": error.details},
            status_code=error.status_code,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        code_map = {
            404: "not_found",
            405: "method_not_allowed",
        }
        return api_error(
            message=error.description,
            error={"code": code_map.get(error.code, "http_error"), "details": None},
            status_code=error.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        logging.getLogger(__name__).exception("Unhandled application exception")
        return api_error(
            message="Internal server error",
            error={"code": "internal_error", "details": None},
            status_code=500,
        )
