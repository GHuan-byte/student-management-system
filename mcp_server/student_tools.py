from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import db


logger = logging.getLogger(__name__)

MAX_KEYWORD_LENGTH = 100
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "students.db"


def get_readonly_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Student database not found: {DB_PATH}")

    database_uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(database_uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _build_student_payload(
    student_number: str,
    name: str,
    gender: str,
    age: int,
    major: str,
    grade: Any,
    phone: str = "",
    email: str = "",
) -> dict[str, Any]:
    return {
        "student_number": student_number,
        "name": name,
        "gender": gender,
        "age": age,
        "major": major,
        "grade": grade,
        "phone": phone,
        "email": email,
    }


def _validate_positive_student_id(student_id: int) -> int:
    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError("student_id must be a positive integer")
    return student_id


def _validate_student_number(student_number: str) -> str:
    if not isinstance(student_number, str):
        raise ValueError("student_number must be a string")

    cleaned_student_number = student_number.strip()
    if not cleaned_student_number:
        raise ValueError("student_number cannot be empty")
    return cleaned_student_number


def _handle_tool_error(tool_name: str, exc: Exception) -> dict[str, Any]:
    logger.exception("Student MCP tool failed: %s", tool_name)
    return {
        "success": False,
        "error": "Internal student tool error",
        "detail": str(exc),
    }


def register_student_tools(mcp: Any) -> None:
    @mcp.tool()
    def database_status() -> dict[str, Any]:
        """Check whether the student database exists and return the currently available table names."""

        try:
            if not DB_PATH.exists():
                return {
                    "success": False,
                    "database_exists": False,
                    "database_path": str(DB_PATH),
                    "tables": [],
                    "message": "Student database file was not found",
                }

            with closing(get_readonly_connection()) as connection:
                rows = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    ORDER BY name
                    """
                ).fetchall()

            return {
                "success": True,
                "database_exists": True,
                "database_path": str(DB_PATH),
                "tables": [row["name"] for row in rows],
                "message": "Student database connection is available",
            }
        except Exception as exc:
            return _handle_tool_error("database_status", exc)

    @mcp.tool()
    def get_student_table_schema() -> dict[str, Any]:
        """Get the current schema of the students table from the connected SQLite database."""

        try:
            with closing(get_readonly_connection()) as connection:
                rows = connection.execute("PRAGMA table_info(students)").fetchall()

            if not rows:
                return {
                    "success": False,
                    "error": "students table not found",
                }

            columns = [
                {
                    "column_id": row["cid"],
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default_value": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ]

            return {
                "success": True,
                "table": "students",
                "column_count": len(columns),
                "columns": columns,
            }
        except Exception as exc:
            return _handle_tool_error("get_student_table_schema", exc)

    @mcp.tool()
    def count_students() -> dict[str, Any]:
        """Count all students currently stored in the student database."""

        try:
            statistics = db.get_student_stats()
            total = int(statistics.get("total_students", 0))
            return {
                "success": True,
                "total": total,
                "message": f"当前共有 {total} 名学生。",
            }
        except Exception as exc:
            return _handle_tool_error("count_students", exc)

    @mcp.tool()
    def list_students() -> dict[str, Any]:
        """List all students currently stored in the student database."""

        try:
            students = db.list_students()
            return {
                "success": True,
                "count": len(students),
                "students": students,
            }
        except Exception as exc:
            return _handle_tool_error("list_students", exc)

    @mcp.tool()
    def search_students(keyword: str) -> dict[str, Any]:
        """Search students using the fields currently supported by db.py, including student_number, name, gender, major, grade, phone, and email."""

        try:
            if not isinstance(keyword, str):
                raise ValueError("keyword must be a string")

            cleaned_keyword = keyword.strip()
            if len(cleaned_keyword) > MAX_KEYWORD_LENGTH:
                raise ValueError(
                    f"keyword must be at most {MAX_KEYWORD_LENGTH} characters"
                )

            students = (
                db.list_students()
                if not cleaned_keyword
                else db.search_students(cleaned_keyword)
            )
            return {
                "success": True,
                "keyword": cleaned_keyword,
                "count": len(students),
                "students": students,
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
            }
        except Exception as exc:
            return _handle_tool_error("search_students", exc)

    @mcp.tool()
    def get_student_by_id(student_id: int) -> dict[str, Any]:
        """Get one student by the internal database ID, not by student_number."""

        try:
            checked_student_id = _validate_positive_student_id(student_id)
            student = db.get_student_by_id(checked_student_id)
            if not student:
                return {
                    "success": False,
                    "error": "Student not found",
                }
            return {
                "success": True,
                "student": student,
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
            }
        except Exception as exc:
            return _handle_tool_error("get_student_by_id", exc)

    @mcp.tool()
    def get_student_by_number(student_number: str) -> dict[str, Any]:
        """Get one student by student number."""

        try:
            cleaned_student_number = _validate_student_number(student_number)
            student = db.get_student_by_number(cleaned_student_number)
            if not student:
                return {
                    "success": False,
                    "error": "Student not found",
                }
            return {
                "success": True,
                "student": student,
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
            }
        except Exception as exc:
            return _handle_tool_error("get_student_by_number", exc)

    @mcp.tool()
    def get_student_stats() -> dict[str, Any]:
        """Get the student statistics currently returned by db.py, including total_students, major_count, grade_count, latest_student_name, and latest_student_time."""

        try:
            statistics = db.get_student_stats()
            return {
                "success": True,
                "statistics": statistics,
            }
        except Exception as exc:
            return _handle_tool_error("get_student_stats", exc)

    @mcp.tool()
    def add_student(
        student_number: str,
        name: str,
        gender: str,
        age: int,
        major: str,
        grade: str,
        phone: str = "",
        email: str = "",
    ) -> dict[str, Any]:
        """Add one student by passing the provided fields through the current db.py validation and insert flow."""

        try:
            payload = _build_student_payload(
                student_number=student_number,
                name=name,
                gender=gender,
                age=age,
                major=major,
                grade=grade,
                phone=phone,
                email=email,
            )
            student = db.add_student(payload)
            return {
                "success": True,
                "message": "Student added successfully",
                "student": student,
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
            }
        except sqlite3.IntegrityError as exc:
            return {
                "success": False,
                "error": "student_number already exists",
                "detail": str(exc),
            }
        except Exception as exc:
            return _handle_tool_error("add_student", exc)

    @mcp.tool()
    def update_student(
        student_id: int,
        student_number: str | None = None,
        name: str | None = None,
        gender: str | None = None,
        age: int | None = None,
        major: str | None = None,
        grade: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Update one student by database ID using the existing db.py update flow after merging partial fields into a complete payload."""

        try:
            checked_student_id = _validate_positive_student_id(student_id)
            existing_student = db.get_student_by_id(checked_student_id)
            if not existing_student:
                return {
                    "success": False,
                    "error": "Student not found",
                }

            updates: dict[str, Any] = {}
            for field_name, field_value in (
                ("student_number", student_number),
                ("name", name),
                ("gender", gender),
                ("age", age),
                ("major", major),
                ("grade", grade),
                ("phone", phone),
                ("email", email),
            ):
                if field_value is not None:
                    updates[field_name] = field_value

            if not updates:
                raise ValueError("At least one field must be provided for update")

            payload = {
                "student_number": updates.get(
                    "student_number", existing_student["student_number"]
                ),
                "name": updates.get("name", existing_student["name"]),
                "gender": updates.get("gender", existing_student["gender"]),
                "age": updates.get("age", existing_student["age"]),
                "major": updates.get("major", existing_student["major"]),
                "grade": updates.get("grade", existing_student["grade"]),
                "phone": updates.get("phone", existing_student.get("phone", "")),
                "email": updates.get("email", existing_student.get("email", "")),
            }

            db.update_student(checked_student_id, payload)
            student = db.get_student_by_id(checked_student_id)
            return {
                "success": True,
                "message": "Student updated successfully",
                "student": student,
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
            }
        except sqlite3.IntegrityError as exc:
            return {
                "success": False,
                "error": "student_number already exists",
                "detail": str(exc),
            }
        except Exception as exc:
            return _handle_tool_error("update_student", exc)

    @mcp.tool()
    def upsert_student(
        student_number: str,
        name: str,
        gender: str,
        age: int,
        major: str,
        grade: str,
        phone: str = "",
        email: str = "",
    ) -> dict[str, Any]:
        """Create a student when the student does not exist, or update the existing student according to the current database upsert rule."""

        try:
            payload = _build_student_payload(
                student_number=student_number,
                name=name,
                gender=gender,
                age=age,
                major=major,
                grade=grade,
                phone=phone,
                email=email,
            )
            operation, student = db.upsert_student(payload)
            return {
                "success": True,
                "message": "Student upsert completed",
                "operation": operation,
                "student": student,
            }
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
            }
        except sqlite3.IntegrityError as exc:
            return {
                "success": False,
                "error": "student_number already exists",
                "detail": str(exc),
            }
        except Exception as exc:
            return _handle_tool_error("upsert_student", exc)


__all__ = [
    "DB_PATH",
    "PROJECT_ROOT",
    "get_readonly_connection",
    "register_student_tools",
]
