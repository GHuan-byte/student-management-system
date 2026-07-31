"""SQLite-backed user account repository."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.database.connection import ConnectionFactory, create_connection_factory
from app.repositories.student_repository import utc_now_iso


class UserRepository:
    """Repository for local login users."""

    def __init__(
        self,
        *,
        database_path: str | Path | None = None,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        if database_path is None and connection_factory is None:
            raise ValueError("UserRepository requires a database path or connection factory.")
        self.database_path = str(database_path) if database_path is not None else None
        self.connection_factory = connection_factory or create_connection_factory(database_path)

    def create_user(self, username: str, password_hash: str, role: str) -> dict[str, Any]:
        timestamp = utc_now_iso()
        connection = self.connection_factory()
        try:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, role, is_active, auth_version,
                        created_at, updated_at, last_login_at
                    ) VALUES (?, ?, ?, 1, 1, ?, ?, NULL)
                    """,
                    [username, password_hash, role, timestamp, timestamp],
                )
                return self._row_by_id(connection, int(cursor.lastrowid))
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        return self._fetch_one("SELECT * FROM users WHERE username = ?", [username])

    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        return self._fetch_one("SELECT * FROM users WHERE id = ?", [user_id])

    def list_users(self) -> list[dict[str, Any]]:
        connection = self.connection_factory()
        try:
            rows = connection.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
            return [self._normalize_row(dict(row)) for row in rows]
        finally:
            connection.close()

    def record_login(self, user_id: int) -> None:
        timestamp = utc_now_iso()
        self._execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            [timestamp, timestamp, user_id],
        )

    def set_active(self, user_id: int, active: bool) -> None:
        self._execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
            [1 if active else 0, utc_now_iso(), user_id],
        )

    def update_role(self, user_id: int, role: str) -> None:
        self._execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            [role, utc_now_iso(), user_id],
        )

    def increment_auth_version(self, user_id: int) -> None:
        self._execute(
            "UPDATE users SET auth_version = auth_version + 1, updated_at = ? WHERE id = ?",
            [utc_now_iso(), user_id],
        )

    def _execute(self, query: str, parameters: list[Any]) -> None:
        connection = self.connection_factory()
        try:
            with connection:
                connection.execute(query, parameters)
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch_one(self, query: str, parameters: list[Any]) -> dict[str, Any] | None:
        connection = self.connection_factory()
        try:
            row = connection.execute(query, parameters).fetchone()
            return self._normalize_row(dict(row)) if row else None
        finally:
            connection.close()

    def _row_by_id(self, connection, user_id: int) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM users WHERE id = ?", [user_id]).fetchone()
        if row is None:
            raise RuntimeError("Failed to load user after write.")
        return self._normalize_row(dict(row))

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["is_active"] = bool(row["is_active"])
        row["auth_version"] = int(row["auth_version"])
        return row
