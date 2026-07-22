"""Student service layer."""

from __future__ import annotations

import sqlite3
from typing import Any

from app.repositories.student_repository import StudentRepository
from app.utils.errors import DuplicateError, NotFoundError, ValidationError

YEAR_LEVEL_VALUES = {
    "\u5927\u4e00",
    "\u5927\u4e8c",
    "\u5927\u4e09",
    "\u5927\u56db",
}


class StudentService:
    """Business logic for student CRUD."""

    required_create_fields = {"student_number", "name"}
    allowed_fields = {
        "student_number",
        "name",
        "gender",
        "age",
        "major",
        "year_level",
        "score",
        "phone",
        "email",
    }
    string_fields = {
        "student_number",
        "name",
        "gender",
        "major",
        "year_level",
        "phone",
        "email",
    }
    nullable_string_fields = {
        "gender",
        "major",
        "year_level",
        "phone",
        "email",
    }
    integer_fields = {"age", "score"}
    protected_fields = {"id", "created_at", "updated_at"}

    def __init__(self, repository: StudentRepository) -> None:
        self.repository = repository

    def list_students(self, keyword: str | None = None) -> list[dict[str, Any]]:
        normalized_keyword = (keyword or "").strip()
        if not normalized_keyword:
            return self.repository.list_students()
        return self.repository.search_students(normalized_keyword)

    def get_student_by_id(self, student_id: int) -> dict[str, Any]:
        student = self.repository.get_student_by_id(student_id)
        if student is None:
            raise NotFoundError("Student not found")
        return student

    def create_student(self, payload: Any) -> dict[str, Any]:
        normalized_payload = self._normalize_payload(payload, partial=False)
        try:
            return self.repository.add_student(normalized_payload)
        except sqlite3.IntegrityError as error:
            raise self._translate_integrity_error(error) from error

    def update_student(self, student_id: int, payload: Any) -> dict[str, Any]:
        normalized_payload = self._normalize_payload(payload, partial=True)
        try:
            student = self.repository.update_student(student_id, normalized_payload)
        except sqlite3.IntegrityError as error:
            raise self._translate_integrity_error(error) from error

        if student is None:
            raise NotFoundError("Student not found")
        return student

    def delete_student(self, student_id: int) -> dict[str, Any]:
        student = self.repository.delete_student(student_id)
        if student is None:
            raise NotFoundError("Student not found")
        return student

    def _normalize_payload(self, payload: Any, *, partial: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object")

        if not payload:
            raise ValidationError("Request body must include at least one field")

        unknown_fields = set(payload) - self.allowed_fields
        protected_fields = set(payload) & self.protected_fields
        if unknown_fields or protected_fields:
            details = {}
            if unknown_fields:
                details["unknown_fields"] = sorted(unknown_fields)
            if protected_fields:
                details["protected_fields"] = sorted(protected_fields)
            raise ValidationError("Payload contains unsupported fields", details=details)

        normalized: dict[str, Any] = {}
        for field, value in payload.items():
            normalized[field] = self._normalize_field(field, value)

        if not partial:
            missing_fields = sorted(
                field for field in self.required_create_fields if normalized.get(field) in (None, "")
            )
            if missing_fields:
                raise ValidationError(
                    "Missing required student fields",
                    details={"missing_fields": missing_fields},
                )

        if partial and not normalized:
            raise ValidationError("Update payload must include at least one editable field")

        return normalized

    def _normalize_field(self, field: str, value: Any) -> Any:
        if field in self.string_fields:
            if value is None:
                if field in self.required_create_fields:
                    raise ValidationError(f"{field} is required")
                return None

            if not isinstance(value, str):
                raise ValidationError(f"{field} must be a string")

            normalized_value = value.strip()
            if field in self.required_create_fields and not normalized_value:
                raise ValidationError(f"{field} is required")
            if field in self.nullable_string_fields and not normalized_value:
                return None
            if field == "year_level":
                if not normalized_value:
                    return None
                if normalized_value not in YEAR_LEVEL_VALUES:
                    raise ValidationError(
                        "year_level must be one of the allowed values",
                        details={"allowed_values": sorted(YEAR_LEVEL_VALUES)},
                    )
            return normalized_value

        if field in self.integer_fields:
            if value == "":
                return None
            if value is None:
                return None
            if isinstance(value, bool):
                raise ValidationError(f"{field} must be an integer")
            if not isinstance(value, int):
                raise ValidationError(f"{field} must be an integer")
            if field == "age" and not 10 <= value <= 100:
                raise ValidationError("age must be between 10 and 100")
            if field == "score" and not 0 <= value <= 100:
                raise ValidationError("score must be between 0 and 100")
            return value

        return value

    def _translate_integrity_error(self, error: sqlite3.IntegrityError) -> ValidationError | DuplicateError:
        message = str(error).lower()
        if "student_number" in message and "unique" in message:
            return DuplicateError("student_number already exists")
        return ValidationError("Student data violates a database constraint")
