"""User account service and bootstrap behavior."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping

from werkzeug.security import check_password_hash, generate_password_hash

from app.logging_config import log_security_event
from app.repositories.user_repository import UserRepository
from app.utils.errors import DuplicateError, ValidationError


ALLOWED_ROLES = frozenset({"viewer", "staff", "admin"})
BOOTSTRAP_ROLES = ("viewer", "staff", "admin")
MIN_PASSWORD_LENGTH = 6


@dataclass(frozen=True)
class AuthenticationResult:
    reason: str
    user: dict[str, Any] | None = None


class UserService:
    """Business rules for local login users."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def normalize_username(self, username: Any) -> str:
        if not isinstance(username, str):
            raise ValidationError("Invalid username")
        normalized = username.strip().lower()
        if not normalized:
            raise ValidationError("Invalid username")
        return normalized

    def validate_password(self, password: Any) -> str:
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError("Invalid password")
        return password

    def validate_role(self, role: Any) -> str:
        if role not in ALLOWED_ROLES:
            raise ValidationError("Invalid role")
        return str(role)

    def create_user(self, username: Any, password: Any, role: Any) -> dict[str, Any]:
        normalized_username = self.normalize_username(username)
        raw_password = self.validate_password(password)
        normalized_role = self.validate_role(role)
        try:
            return self.repository.create_user(
                normalized_username,
                generate_password_hash(raw_password),
                normalized_role,
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateError("Duplicate username") from exc

    def get_user_by_username(self, username: Any) -> dict[str, Any] | None:
        return self.repository.get_by_username(self.normalize_username(username))

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        return self.repository.get_by_id(user_id)

    def authenticate(self, username: Any, password: Any) -> dict[str, Any] | None:
        result = self.authenticate_with_result(username, password)
        if result.reason != "success":
            return None
        return result.user

    def authenticate_with_result(self, username: Any, password: Any) -> AuthenticationResult:
        try:
            normalized = self.normalize_username(username)
        except ValidationError:
            return AuthenticationResult(reason="invalid_credentials")
        if not isinstance(password, str):
            return AuthenticationResult(reason="invalid_credentials")
        user = self.repository.get_by_username(normalized)
        if user is None:
            return AuthenticationResult(reason="invalid_credentials")
        if not user["is_active"]:
            return AuthenticationResult(reason="inactive_account", user=user)
        if not check_password_hash(user["password_hash"], password):
            return AuthenticationResult(reason="invalid_credentials")
        return AuthenticationResult(reason="success", user=user)

    def record_login(self, user_id: int) -> None:
        self.repository.record_login(user_id)

    def ensure_bootstrap_users(self, config: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        if not bool(config.get("BOOTSTRAP_DEFAULT_USERS_ENABLED")):
            return {"created": [], "skipped": []}

        entries = self._bootstrap_entries(config)
        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for entry in entries:
            existing = self.repository.get_by_username(entry["username"])
            if existing is not None:
                event_data = {
                    "username": existing["username"],
                    "role": existing["role"],
                    "outcome": "skipped",
                    "reason": "already_exists",
                }
                log_security_event("bootstrap_user_skipped", metadata=event_data)
                skipped.append(event_data)
                continue
            user = self.create_user(entry["username"], entry["password"], entry["role"])
            event_data = {"username": user["username"], "role": user["role"], "outcome": "created"}
            log_security_event("bootstrap_user_created", metadata=event_data)
            created.append(event_data)
        return {"created": created, "skipped": skipped}

    def _bootstrap_entries(self, config: Mapping[str, Any]) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        seen: set[str] = set()
        for role in BOOTSTRAP_ROLES:
            prefix = f"BOOTSTRAP_{role.upper()}"
            try:
                username = self.normalize_username(config.get(f"{prefix}_USERNAME"))
                password = self.validate_password(config.get(f"{prefix}_PASSWORD"))
            except ValidationError as exc:
                raise ValueError(f"Invalid bootstrap configuration for role {role}") from exc
            if username in seen:
                raise ValueError("Invalid bootstrap configuration: duplicate username")
            seen.add(username)
            entries.append({"username": username, "password": password, "role": role})
        return entries
