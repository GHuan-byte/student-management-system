"""SQLite-backed student repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Any

from app.database.connection import ConnectionFactory, create_connection_factory


def utc_now_iso() -> str:
    """Return the current UTC timestamp in a stable ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StudentRepository:
    """Repository for student CRUD operations."""

    writable_fields = (
        "student_number",
        "name",
        "gender",
        "age",
        "major",
        "year_level",
        "score",
        "phone",
        "email",
    )
    sortable_fields = {
        "student_number": "student_number",
        "name": "name",
        "gender": "gender",
        "age": "age",
        "major": "major",
        "year_level": "year_level",
        "score": "score",
    }
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

    def list_students(
        self,
        *,
        keyword: str = "",
        page: int = 1,
        page_size: int = 15,
        sort_by: str = "student_number",
        sort_order: str = "asc",
    ) -> dict[str, Any]:
        normalized_keyword = keyword.strip()
        where_clause, parameters = self._build_search_filter(normalized_keyword)
        total = self.count_students(keyword=normalized_keyword)
        total_pages = ceil(total / page_size) if total else 0
        sort_column = self.sortable_fields.get(sort_by)
        if sort_column is None:
            raise ValueError(f"Unsupported sort field: {sort_by}")

        normalized_sort_order = str(sort_order).lower()
        if normalized_sort_order not in {"asc", "desc"}:
            raise ValueError(f"Unsupported sort order: {sort_order}")

        offset = (page - 1) * page_size
        query = f"""
            SELECT id, student_number, name, gender, age, major, year_level, score, phone, email,
                   created_at, updated_at
            FROM students
            {where_clause}
            ORDER BY {sort_column} {normalized_sort_order.upper()}, id ASC
            LIMIT ? OFFSET ?
        """
        rows = self._fetch_all(query, [*parameters, page_size, offset])
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "sort_by": sort_by,
            "sort_order": normalized_sort_order,
        }

    def count_students(self, *, keyword: str = "") -> int:
        normalized_keyword = keyword.strip()
        where_clause, parameters = self._build_search_filter(normalized_keyword)
        query = f"SELECT COUNT(*) AS total FROM students {where_clause}"
        connection = self.connection_factory()
        try:
            row = connection.execute(query, parameters).fetchone()
            return int(row["total"]) if row else 0
        finally:
            connection.close()

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
            **{field: payload.get(field) for field in self.writable_fields},
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

    def batch_delete_students(self, student_ids: list[int]) -> int:
        placeholders = ", ".join("?" for _ in student_ids)
        query = f"DELETE FROM students WHERE id IN ({placeholders})"
        connection = self.connection_factory()
        try:
            with connection:
                cursor = connection.execute(query, student_ids)
                return int(cursor.rowcount)
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _build_search_filter(self, keyword: str) -> tuple[str, list[Any]]:
        if not keyword:
            return "", []

        like_value = f"%{keyword}%"
        where_clause = " OR ".join(f"{field} LIKE ?" for field in self.searchable_fields)
        return f"WHERE {where_clause}", [like_value] * len(self.searchable_fields)

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
