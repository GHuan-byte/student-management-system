"""Shared, idempotent logging configuration for Flask and MCP."""

from __future__ import annotations

import copy
import logging
import logging.config
import re
import traceback
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any, Iterator, Mapping

from flask import Flask, g

from app.config import DEV_SECRET_KEY, PLACEHOLDER_SECRET_KEY


MANAGED_HANDLER_ATTRIBUTE = "_student_management_managed"
APPLICATION_LOGGERS = ("app", "mcp_server")
REQUEST_ID: ContextVar[str] = ContextVar("student_management_request_id", default="-")
REDACTED = "[REDACTED]"
STUDENT_RECORD = "[STUDENT_RECORD_REDACTED]"
_SENSITIVE_KEYS = frozenset({
    "password", "password_hash", "api_key", "authorization", "authorization_header",
    "cookie", "cookies", "session", "session_id", "csrf_token",
    "confirmation_token", "ai_confirmation_token",
})
_STUDENT_FIELDS = frozenset({
    "student_number", "name", "gender", "age", "major", "year_level",
    "score", "phone", "email",
})
_STRING_SECRET_PATTERN = re.compile(
    r"(?i)\b(password(?:[\s_-]*hash)?|api[\s_-]*key|authorization(?:[\s_-]*header)?|cookies?|"
    r"session(?:[\s_-]*(?:id|token))?|csrf(?:[\s_-]*token)?|"
    r"(?:ai[\s_-]*)?confirmation[\s_-]*token)"
    r"(\s*(?:[=:]\s*|\s+))([^\s,;]+)"
)
_AUTHORIZATION_HEADER_PATTERN = re.compile(
    r"(?i)\b(authorization(?:[\s_-]*header)?)(\s*(?:[=:]\s*|\s+))"
    r"([!#$%&'*+\-.^_`|~0-9a-z]+)(?:\s+[^;|\r\n]*)?"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


def current_request_id() -> str:
    """Return the active request/correlation identifier or its stable fallback."""
    return REQUEST_ID.get()


@contextmanager
def correlation_context(request_id: str) -> Iterator[None]:
    """Temporarily associate non-request work with an explicit identifier."""
    token = REQUEST_ID.set(request_id or "-")
    try:
        yield
    finally:
        REQUEST_ID.reset(token)


def _is_student_record(value: Mapping[Any, Any]) -> bool:
    keys = {str(key).lower() for key in value}
    return _STUDENT_FIELDS.issubset(keys)


def _is_sensitive_key(key: Any) -> bool:
    normalized = re.sub(r"[\s-]+", "_", str(key).lower())
    return normalized in _SENSITIVE_KEYS or normalized.endswith("_api_key")


def sanitize_log_value(value: Any) -> Any:
    """Return a safe copy of a log value without mutating caller-owned data."""
    if isinstance(value, Mapping):
        if _is_student_record(value):
            return STUDENT_RECORD
        return {
            key: REDACTED if _is_sensitive_key(key) else sanitize_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_log_value(item) for item in value)
    if isinstance(value, set):
        return {sanitize_log_value(item) for item in value}
    if isinstance(value, str):
        sanitized = value.replace(DEV_SECRET_KEY, REDACTED).replace(PLACEHOLDER_SECRET_KEY, REDACTED)
        sanitized = _AUTHORIZATION_HEADER_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)} {REDACTED}",
            sanitized,
        )
        sanitized = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", sanitized)
        sanitized = _STRING_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", sanitized)
        return sanitized
    return value


def _safe_log_message(message: Any, arguments: Any) -> str:
    """Render a log message with sanitized arguments while preserving format compatibility."""
    if arguments:
        try:
            rendered = str(message) % sanitize_log_value(arguments)
        except Exception:
            rendered = f"{sanitize_log_value(message)} {REDACTED}"
    else:
        rendered = str(sanitize_log_value(message))
    return str(sanitize_log_value(rendered))


class StandardFieldsFilter(logging.Filter):
    """Inject standard fields and redact structured log values."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = sanitize_log_value(getattr(record, "request_id", current_request_id())) or "-"
        record.event = sanitize_log_value(getattr(record, "event", "-")) or "-"
        record.msg = _safe_log_message(record.msg, record.args)
        record.args = ()
        for key, value in tuple(record.__dict__.items()):
            if key not in logging.LogRecord(None, 0, "", 0, "", (), None).__dict__:
                setattr(record, key, sanitize_log_value(value))
        return True


class SafeFormatter(logging.Formatter):
    """Format a safe record copy while preserving sanitized traceback structure."""

    def format(self, record: logging.LogRecord) -> str:
        safe_record = copy.copy(record)
        StandardFieldsFilter().filter(safe_record)
        if safe_record.exc_info:
            safe_record.exc_text = sanitize_log_value("".join(traceback.format_exception(*safe_record.exc_info)))
        return super().format(safe_record)


def _close_managed_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False):
            logger.removeHandler(handler)
            handler.flush()
            handler.close()


def _unmanaged_logger_states() -> dict[str, tuple[list[logging.Handler], int, bool, bool, list[logging.Filter], logging.Logger]]:
    """Snapshot logger state that the shared policy does not own."""
    return {
        name: (
            list(logger.handlers),
            logger.level,
            logger.propagate,
            logger.disabled,
            list(logger.filters),
            logger.parent,
        )
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger) and name not in APPLICATION_LOGGERS
    }


def _restore_unmanaged_logger_states(
    states: Mapping[str, tuple[list[logging.Handler], int, bool, bool, list[logging.Filter], logging.Logger]],
) -> None:
    """Restore external logger state changed by non-incremental dictConfig."""
    for name, (handlers, level, propagate, disabled, filters, parent) in states.items():
        logger = logging.root.manager.loggerDict.get(name)
        if not isinstance(logger, logging.Logger):
            continue
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled
        logger.filters[:] = filters
        logger.parent = parent


def _configure_shared_logging(configuration: Mapping[str, Any]) -> None:
    """Apply dictConfig while preserving unowned application logger handlers."""
    unmanaged_application_handlers = {
        logger_name: [
            handler
            for handler in logging.getLogger(logger_name).handlers
            if not getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)
        ]
        for logger_name in APPLICATION_LOGGERS
    }
    unmanaged_logger_states = _unmanaged_logger_states()
    for logger_name in APPLICATION_LOGGERS:
        _close_managed_handlers(logging.getLogger(logger_name))

    all_handler_references = list(logging._handlerList)
    unmanaged_references = [
        reference
        for reference in all_handler_references
        if (handler := reference()) is not None
        and not getattr(handler, MANAGED_HANDLER_ATTRIBUTE, False)
    ]
    unmanaged_handler_set = {reference() for reference in unmanaged_references if reference() is not None}
    unmanaged_names = {
        name: handler
        for name, handler in logging._handlers.items()
        if handler in unmanaged_handler_set
    }
    logging._handlerList[:] = [
        reference
        for reference in all_handler_references
        if reference not in unmanaged_references
    ]
    try:
        logging.config.dictConfig(configuration)
    finally:
        logging._handlerList.extend(
            reference for reference in unmanaged_references if reference() is not None
        )
        for name, handler in unmanaged_names.items():
            logging._handlers.setdefault(name, handler)

    _restore_unmanaged_logger_states(unmanaged_logger_states)

    for logger_name in APPLICATION_LOGGERS:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            setattr(handler, MANAGED_HANDLER_ATTRIBUTE, True)
        for handler in unmanaged_application_handlers[logger_name]:
            if handler not in logger.handlers:
                logger.addHandler(handler)


def _configuration(config: Mapping[str, Any]) -> dict[str, Any]:
    level = str(config.get("LOG_LEVEL", "INFO")).upper()
    handlers: dict[str, Any] = {}
    handler_names: list[str] = []
    if config.get("LOG_CONSOLE_ENABLED", True):
        handlers["managed_console"] = {
            "class": "logging.StreamHandler", "level": level, "formatter": "standard",
            "filters": ["standard_fields"], "stream": "ext://sys.stderr",
        }
        handler_names.append("managed_console")
    if config.get("LOG_FILE_ENABLED"):
        path = Path(str(config["LOG_FILE_PATH"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers["managed_file"] = {
            "class": "logging.handlers.RotatingFileHandler", "level": level,
            "formatter": "standard", "filters": ["standard_fields"], "filename": str(path),
            "maxBytes": int(config["LOG_FILE_MAX_BYTES"]),
            "backupCount": int(config["LOG_FILE_BACKUP_COUNT"]), "encoding": "utf-8",
        }
        handler_names.append("managed_file")
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"standard_fields": {"()": StandardFieldsFilter}},
        "formatters": {
            "standard": {
                "()": SafeFormatter,
                "format": "timestamp=%(asctime)s level=%(levelname)s logger=%(name)s request_id=%(request_id)s event=%(event)s message=%(message)s",
            }
        },
        "handlers": handlers,
        "loggers": {
            logger_name: {"handlers": handler_names, "level": level, "propagate": False}
            for logger_name in APPLICATION_LOGGERS
        },
    }


def _install_request_context(app: Flask) -> None:
    if app.extensions.get("logging_request_context_installed"):
        return

    @app.before_request
    def _set_request_id() -> None:
        token = REQUEST_ID.set(uuid.uuid4().hex)
        g._logging_request_id_token = token

    @app.teardown_request
    def _reset_request_id(_error: BaseException | None) -> None:
        token = g.pop("_logging_request_id_token", None)
        if isinstance(token, Token):
            REQUEST_ID.reset(token)

    app.extensions["logging_request_context_installed"] = True


def configure_logging(app: Flask) -> None:
    """Configure managed Flask and MCP loggers after configuration is finalized."""
    configuration = _configuration(app.config)
    _configure_shared_logging(configuration)
    _install_request_context(app)
    app.extensions.setdefault("logging_dictconfigs", []).append(configuration)
    app.logger.info(
        "Application logging configured",
        extra={"event": "application_logging_configured"},
    )


def configure_mcp_logging(config: Mapping[str, Any] | None = None) -> None:
    """Configure the shared policy for stdio MCP before protocol startup."""
    resolved = {"LOG_LEVEL": "INFO", "LOG_CONSOLE_ENABLED": True, "LOG_FILE_ENABLED": False}
    if config:
        resolved.update(config)
    _configure_shared_logging(_configuration(resolved))


def log_security_event(event: str, *, level: int = logging.INFO, metadata: Any = None, **extra: Any) -> None:
    """Log a future authentication/security event through the shared policy."""
    logging.getLogger("app.security").log(
        level,
        "security event",
        extra={"event": event, "metadata": metadata or {}, **extra},
    )
