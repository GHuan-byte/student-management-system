"""SQLite-backed student repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.database.connection import ConnectionFactory, create_connection_factory


def utc_now_iso() -> str:
    """Return the current UTC timestamp in a stable ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StudentRepository:
    """Repository for student CRUD operations."""

    searchable_fields = (
        "student_number",
        "name",
        "major",
        "phone",
        "email",
    )

    def __init__(
        self,
        *,
        database_path: str | Path | None = None,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        if database_path is None and connection_factory is None:
            raise ValueError("StudentRepository requires a database path or connection factory.")

        self.database_path = str(database_path) if database_path is not None else None
        self.connection_factory = connection_factory or create_connection_factory(database_path)

    def list_students(self) -> list[dict[str, Any]]:
        query = """
            SELECT id, student_number, name, gender, age, major, year_level, score, phone, email,
                   created_at, updated_at
            FROM students
            ORDER BY id ASC
        """
        return self._fetch_all(query)

    def search_students(self, keyword: str) -> list[dict[str, Any]]:
        like_value = f"%{keyword}%"
        where_clause = " OR ".join(f"{field} LIKE ?" for field in self.searchable_fields)
        query = f"""
            SELECT id, student_number, name, gender, age, major, year_level, score, phone, email,
                   created_at, updated_at
            FROM students
            WHERE {where_clause}
            ORDER BY id ASC
        """
        parameters = [like_value] * len(self.searchable_fields)
        return self._fetch_all(query, parameters)

    def get_student_by_id(self, student_id: int) -> dict[str, Any] | None:
        query = """
            SELECT id, student_number, name, gender, age, major, year_level, score, phone, email,
                   created_at, updated_at
            FROM students
            WHERE id = ?
        """
        return self._fetch_one(query, [student_id])

    def get_student_by_number(self, student_number: str) -> dict[str, Any] | None:
        query = """
            SELECT id, student_number, name, gender, age, major, year_level, score, phone, email,
                   created_at, updated_at
            FROM students
            WHERE student_number = ?
        """
        return self._fetch_one(query, [student_number])

    def add_student(self, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = utc_now_iso()
        parameters = {
            **payload,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        query = """
            INSERT INTO students (
                student_number, name, gender, age, major, year_level, score, phone, email,
                created_at, updated_at
            ) VALUES (
                :student_number, :name, :gender, :age, :major, :year_level, :score, :phone, :email,
                :created_at, :updated_at
            )
        """
        return self._write_and_fetch(query, parameters)

    def update_student(self, student_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        existing_student = self.get_student_by_id(student_id)
        if existing_student is None:
            return None

        assignments = [f"{field} = :{field}" for field in payload]
        parameters = {
            **payload,
            "student_id": student_id,
            "updated_at": utc_now_iso(),
        }
        assignments.append("updated_at = :updated_at")
        query = f"""
            UPDATE students
            SET {", ".join(assignments)}
            WHERE id = :student_id
        """
        return self._write_and_fetch(query, parameters, student_id=student_id)

    def delete_student(self, student_id: int) -> dict[str, Any] | None:
        existing_student = self.get_student_by_id(student_id)
        if existing_student is None:
            return None

        query = "DELETE FROM students WHERE id = ?"
        connection = self.connection_factory()
        try:
            with connection:
                connection.execute(query, [student_id])
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

        return existing_student

    def _fetch_all(
        self,
        query: str,
        parameters: list[Any] | tuple[Any, ...] | None = None,
    ) -> list[dict[str, Any]]:
        connection = self.connection_factory()
        try:
            cursor = connection.execute(query, parameters or [])
            return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _fetch_one(
        self,
        query: str,
        parameters: list[Any] | tuple[Any, ...] | None = None,
    ) -> dict[str, Any] | None:
        connection = self.connection_factory()
        try:
            cursor = connection.execute(query, parameters or [])
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def _write_and_fetch(
        self,
        query: str,
        parameters: dict[str, Any],
        *,
        student_id: int | None = None,
    ) -> dict[str, Any]:
        connection = self.connection_factory()
        try:
            with connection:
                cursor = connection.execute(query, parameters)
                resolved_id = student_id or int(cursor.lastrowid)
                row = connection.execute(
                    """
                    SELECT id, student_number, name, gender, age, major, year_level, score,
                           phone, email, created_at, updated_at
                    FROM students
                    WHERE id = ?
                    """,
                    [resolved_id],
                ).fetchone()
                if row is None:
                    raise RuntimeError("Failed to load student after write.")
                return dict(row)
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()
