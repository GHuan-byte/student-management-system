"""Authentication, CSRF, and authorization helpers."""

from __future__ import annotations

import hmac
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, g, redirect, render_template, request, session, url_for

from app.database.schema import initialize_database
from app.logging_config import log_security_event
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.utils.response import api_error


READ_ROLES = frozenset({"viewer", "staff", "admin"})
WRITE_ROLES = frozenset({"staff", "admin"})
ADMIN_ROLES = frozenset({"admin"})

ENDPOINT_ROLES: dict[str, frozenset[str]] = {
    "pages.dashboard_page": READ_ROLES,
    "pages.students_page": READ_ROLES,
    "students.list_students": READ_ROLES,
    "students.get_student_stats": READ_ROLES,
    "students.get_student": READ_ROLES,
    "students.create_student": WRITE_ROLES,
    "students.update_student": WRITE_ROLES,
    "students.delete_student": ADMIN_ROLES,
    "students.batch_delete_students": ADMIN_ROLES,
    "chat.chat": READ_ROLES,
    "chat.confirm_chat_action": READ_ROLES,
    "auth.logout": READ_ROLES,
}

PUBLIC_ENDPOINTS = frozenset({
    "auth.login",
    "auth.login_post",
    "health.health_check",
    "static",
})

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
STAFF_AI_WRITE_TOOLS = frozenset({"add_student", "update_student", "upsert_student"})
ADMIN_AI_WRITE_TOOLS = frozenset({"delete_student", "batch_delete_students"})


def create_user_service(database_path: str) -> UserService:
    return UserService(UserRepository(database_path=database_path))


def initialize_auth_storage_and_bootstrap(app: Flask) -> None:
    database_path = Path(app.config["DATABASE_PATH"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(database_path)
    service = create_user_service(str(database_path))
    service.ensure_bootstrap_users(app.config)


def register_auth(app: Flask) -> None:
    """Install current-user, CSRF, and authorization behavior."""

    @app.context_processor
    def inject_auth_context() -> dict[str, Any]:
        return {
            "current_user": getattr(g, "current_user", None),
            "csrf_token": ensure_csrf_token,
        }

    @app.before_request
    def load_and_authorize_current_user():
        g.current_user = None
        user_id = session.get("user_id")
        if user_id is not None:
            service = app.extensions["user_service_factory"]()
            user = service.get_user_by_id(int(user_id))
            if (
                user is None
                or not user["is_active"]
                or int(session.get("auth_version", -1)) != int(user["auth_version"])
            ):
                session.clear()
                log_security_event("session_invalidated", metadata={"endpoint": request.endpoint})
            else:
                g.current_user = user

        endpoint = request.endpoint
        if endpoint in PUBLIC_ENDPOINTS or endpoint is None:
            if request.method not in SAFE_METHODS and endpoint == "auth.login_post":
                csrf_response = _require_csrf()
                if csrf_response is not None:
                    return csrf_response
            return None

        required_roles = ENDPOINT_ROLES.get(endpoint)
        if required_roles is None:
            return None

        if g.current_user is None:
            log_security_event(
                "anonymous_access_rejected",
                metadata={
                    "endpoint": endpoint,
                    "method": request.method,
                    "outcome": "rejected",
                    "reason": "missing_login",
                },
            )
            if _is_api_request():
                return api_error(
                    message="Unauthorized",
                    error={"code": "unauthorized", "details": None},
                    status_code=401,
                )
            return redirect(url_for("auth.login", next=_safe_next_value(request.full_path)))

        if request.method not in SAFE_METHODS:
            csrf_response = _require_csrf()
            if csrf_response is not None:
                return csrf_response

        if g.current_user["role"] not in required_roles:
            log_security_event(
                "authorization_denied",
                metadata={
                    "user_id": g.current_user["id"],
                    "username": g.current_user["username"],
                    "role": g.current_user["role"],
                    "endpoint": endpoint,
                    "outcome": "denied",
                },
            )
            if _is_api_request():
                return api_error(
                    message="Forbidden",
                    error={"code": "forbidden", "details": None},
                    status_code=403,
                )
            return render_template("forbidden.html"), 403
        return None


def ensure_csrf_token() -> str:
    token = session.get("csrf_token")
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf_token(submitted: str | None) -> bool:
    expected = session.get("csrf_token")
    return (
        isinstance(expected, str)
        and isinstance(submitted, str)
        and bool(submitted)
        and hmac.compare_digest(expected, submitted)
    )


def login_user(user: dict[str, Any]) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["auth_version"] = user["auth_version"]
    ensure_csrf_token()


def logout_user() -> None:
    session.clear()


def safe_redirect_target(value: str | None) -> str:
    if not value:
        return "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return "/"
    if value.startswith("//"):
        return "/"
    return value


def can_confirm_action(role: str, tool_name: Any) -> bool:
    if role == "admin" and tool_name in (STAFF_AI_WRITE_TOOLS | ADMIN_AI_WRITE_TOOLS):
        return True
    if role == "staff" and tool_name in STAFF_AI_WRITE_TOOLS:
        return True
    return False


def role_can_execute_ai_tool(role: str, tool_name: Any) -> bool:
    return can_confirm_action(role, tool_name)


def _safe_next_value(value: str) -> str:
    if value.endswith("?"):
        value = value[:-1]
    return safe_redirect_target(value)


def _csrf_from_request() -> str | None:
    return request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")


def _require_csrf():
    if validate_csrf_token(_csrf_from_request()):
        return None
    log_security_event("csrf_rejected", metadata={"endpoint": request.endpoint, "outcome": "rejected"})
    if _is_api_request():
        return api_error(
            message="Forbidden",
            error={"code": "forbidden", "details": None},
            status_code=403,
        )
    return render_template("forbidden.html"), 403


def _is_api_request() -> bool:
    return request.path.startswith("/api/")
