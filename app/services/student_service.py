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

    default_page = 1
    default_page_size = 15
    max_page_size = 50
    max_batch_delete_ids = 50
    default_sort_by = "student_number"
    default_sort_order = "asc"
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

    def list_students(
        self,
        *,
        keyword: str | None = None,
        page: Any = None,
        page_size: Any = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        normalized_keyword = (keyword or "").strip()
        resolved_page = self._normalize_page(page)
        resolved_page_size = self._normalize_page_size(page_size)
        resolved_sort_by = self._normalize_sort_by(sort_by)
        resolved_sort_order = self._normalize_sort_order(sort_order)
        return self.repository.list_students(
            keyword=normalized_keyword,
            page=resolved_page,
            page_size=resolved_page_size,
            sort_by=resolved_sort_by,
            sort_order=resolved_sort_order,
        )

    def count_students(self, *, keyword: str | None = None) -> dict[str, int]:
        normalized_keyword = (keyword or "").strip()
        return {"total_students": self.repository.count_students(keyword=normalized_keyword)}

    def get_student_by_id(self, student_id: int) -> dict[str, Any]:
        student = self.repository.get_student_by_id(student_id)
        if student is None:
            raise NotFoundError("Student not found")
        return student

    def get_student_by_number(self, student_number: Any) -> dict[str, Any]:
        normalized_student_number = self._normalize_lookup_student_number(student_number)
        student = self.repository.get_student_by_number(normalized_student_number)
        if student is None:
            raise NotFoundError("Student not found")
        return student

    def search_students(
        self,
        *,
        keyword: Any,
        page: Any = None,
        page_size: Any = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
    ) -> dict[str, Any]:
        normalized_keyword = self._normalize_required_keyword(keyword)
        return self.list_students(
            keyword=normalized_keyword,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def create_student(self, payload: Any) -> dict[str, Any]:
        normalized_payload = self._normalize_payload(payload, partial=False)
        try:
            return self.repository.add_student(normalized_payload)
        except sqlite3.IntegrityError as error:
            raise self._translate_integrity_error(error) from error

    def upsert_student(self, payload: Any) -> dict[str, Any]:
        normalized_payload = self._normalize_payload(payload, partial=False)
        normalized_student_number = normalized_payload["student_number"]
        existing_student = self.repository.get_student_by_number(normalized_student_number)

        if existing_student is None:
            try:
                created_student = self.repository.add_student(normalized_payload)
            except sqlite3.IntegrityError as error:
                raise self._translate_integrity_error(error) from error
            return {
                "action": "created",
                "student": created_student,
            }

        update_payload = {
            field: value
            for field, value in normalized_payload.items()
            if field != "student_number"
        }
        try:
            updated_student = self.repository.update_student(existing_student["id"], update_payload)
        except sqlite3.IntegrityError as error:
            raise self._translate_integrity_error(error) from error

        if updated_student is None:
            raise NotFoundError("Student not found")
        return {
            "action": "updated",
            "student": updated_student,
        }

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

    def batch_delete_students(self, payload: Any) -> dict[str, int]:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object")

        student_ids = payload.get("student_ids")
        if not isinstance(student_ids, list) or not student_ids:
            raise ValidationError("student_ids must be a non-empty array")

        normalized_ids: list[int] = []
        seen: set[int] = set()

        for raw_id in student_ids:
            if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
                raise ValidationError("student_ids must contain positive integers only")
            if raw_id not in seen:
                seen.add(raw_id)
                normalized_ids.append(raw_id)

        if len(normalized_ids) > self.max_batch_delete_ids:
            raise ValidationError(
                "student_ids must contain no more than 50 unique IDs",
                details={"max_unique_ids": self.max_batch_delete_ids},
            )

        deleted_count = self.repository.batch_delete_students(normalized_ids)
        return {
            "requested_count": len(normalized_ids),
            "deleted_count": deleted_count,
        }

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

    def _normalize_page(self, value: Any) -> int:
        if value in (None, ""):
            return self.default_page
        if isinstance(value, bool):
            raise ValidationError("page must be an integer")
        try:
            page = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError("page must be an integer") from error
        if page < 1:
            raise ValidationError("page must be greater than or equal to 1")
        return page

    def _normalize_page_size(self, value: Any) -> int:
        if value in (None, ""):
            return self.default_page_size
        if isinstance(value, bool):
            raise ValidationError("page_size must be an integer")
        try:
            page_size = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError("page_size must be an integer") from error
        if page_size < 1 or page_size > self.max_page_size:
            raise ValidationError("page_size must be between 1 and 50")
        return page_size

    def _normalize_sort_by(self, value: str | None) -> str:
        if value in (None, ""):
            return self.default_sort_by
        if value not in self.repository.sortable_fields:
            raise ValidationError(
                "sort_by must be one of the approved fields",
                details={"allowed_sort_fields": sorted(self.repository.sortable_fields)},
            )
        return value

    def _normalize_sort_order(self, value: str | None) -> str:
        if value in (None, ""):
            return self.default_sort_order
        normalized = str(value).lower()
        if normalized not in {"asc", "desc"}:
            raise ValidationError(
                "sort_order must be asc or desc",
                details={"allowed_sort_orders": ["asc", "desc"]},
            )
        return normalized

    def _normalize_required_keyword(self, value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError("keyword must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValidationError("keyword must be a non-empty string")
        return normalized

    def _normalize_lookup_student_number(self, value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError("student_number must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValidationError("student_number must be a non-empty string")
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
