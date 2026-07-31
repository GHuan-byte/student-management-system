"""Tests for local user storage and service behavior."""

from __future__ import annotations

import sqlite3

import pytest

from app.database.connection import open_connection
from app.database.schema import initialize_database
from app.utils.errors import DuplicateError, ValidationError


def _table_columns(database_path, table_name: str) -> set[str]:
    connection = open_connection(database_path)
    try:
        return {row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")}
    finally:
        connection.close()


def test_initialize_database_creates_users_without_deleting_students(tmp_path):
    from app.repositories.student_repository import StudentRepository

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    student = StudentRepository(database_path=database_path).add_student({
        "student_number": "001",
        "name": "Alice",
    })

    initialize_database(database_path)

    assert _table_columns(database_path, "users") == {
        "id",
        "username",
        "password_hash",
        "role",
        "is_active",
        "auth_version",
        "created_at",
        "updated_at",
        "last_login_at",
    }
    assert StudentRepository(database_path=database_path).get_student_by_id(student["id"])["student_number"] == "001"


def test_users_table_rejects_invalid_role(tmp_path):
    database_path = tmp_path / "auth.db"
    initialize_database(database_path)

    connection = open_connection(database_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO users (
                    username, password_hash, role, is_active, auth_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("bad", "hash", "owner", 1, 1, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
    finally:
        connection.close()


def test_user_service_normalizes_hashes_and_authenticates(tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    service = UserService(UserRepository(database_path=database_path))

    created = service.create_user("  Viewer  ", "secret1", "viewer")

    assert created["username"] == "viewer"
    assert created["role"] == "viewer"
    assert created["is_active"] is True
    assert created["auth_version"] == 1
    assert created["last_login_at"] is None
    assert created["password_hash"] != "secret1"
    assert service.authenticate("VIEWER", "secret1")["username"] == "viewer"
    assert service.authenticate("viewer", "wrong") is None


def test_user_service_returns_explicit_authentication_reasons(tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    repository = UserRepository(database_path=database_path)
    service = UserService(repository)
    created = service.create_user("viewer", "secret1", "viewer")

    missing = service.authenticate_with_result("missing", "secret1")
    wrong = service.authenticate_with_result("viewer", "wrong")
    success = service.authenticate_with_result("viewer", "secret1")
    repository.set_active(created["id"], False)
    inactive = service.authenticate_with_result("viewer", "secret1")

    assert missing.reason == "invalid_credentials"
    assert missing.user is None
    assert wrong.reason == "invalid_credentials"
    assert wrong.user is None
    assert success.reason == "success"
    assert success.user["username"] == "viewer"
    assert inactive.reason == "inactive_account"
    assert inactive.user["username"] == "viewer"
    assert "password_hash" in inactive.user


def test_user_service_rejects_duplicate_invalid_role_and_weak_password(tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    service = UserService(UserRepository(database_path=database_path))
    service.create_user("staff", "secret1", "staff")

    with pytest.raises(DuplicateError):
        service.create_user(" STAFF ", "secret2", "staff")
    with pytest.raises(ValidationError):
        service.create_user("badrole", "secret1", "owner")
    with pytest.raises(ValidationError):
        service.create_user("short", "12345", "viewer")


def test_user_service_inactive_and_auth_version_behaviors(tmp_path):
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    database_path = tmp_path / "auth.db"
    initialize_database(database_path)
    repository = UserRepository(database_path=database_path)
    service = UserService(repository)

    created = service.create_user("admin", "secret1", "admin")
    service.record_login(created["id"])
    logged_in = service.get_user_by_id(created["id"])
    assert logged_in["last_login_at"] is not None

    repository.set_active(created["id"], False)
    assert service.authenticate("admin", "secret1") is None
    inactive = service.get_user_by_id(created["id"])
    assert inactive["is_active"] is False

    repository.set_active(created["id"], True)
    repository.increment_auth_version(created["id"])
    updated = service.get_user_by_id(created["id"])
    assert updated["auth_version"] == 2
