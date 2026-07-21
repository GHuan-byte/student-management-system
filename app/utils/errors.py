"""Application exception hierarchy."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", *, details: Any = None) -> None:
        super().__init__(
            message,
            code="not_found",
            status_code=404,
            details=details,
        )


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", *, details: Any = None) -> None:
        super().__init__(
            message,
            code="validation_error",
            status_code=400,
            details=details,
        )


class DuplicateError(AppError):
    def __init__(self, message: str = "Duplicate resource", *, details: Any = None) -> None:
        super().__init__(
            message,
            code="duplicate",
            status_code=409,
            details=details,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", *, details: Any = None) -> None:
        super().__init__(
            message,
            code="forbidden",
            status_code=403,
            details=details,
        )
