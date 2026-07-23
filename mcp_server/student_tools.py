"""MCP student tool definitions."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Callable, Literal

from pydantic import Field, WithJsonSchema

from app.services.student_service import StudentService
from mcp_server.result import mcp_paginated, mcp_result_from_exception, mcp_success

logger = logging.getLogger(__name__)

ToolServiceFactory = Callable[[], StudentService]
YearLevel = Literal["大一", "大二", "大三", "大四"]
SortBy = Literal["student_number", "name", "gender", "age", "major", "year_level", "score"]
SortOrder = Literal["asc", "desc"]
PositiveStudentId = Annotated[int, Field(description="Positive student ID.", gt=0)]
BatchDeleteStudentIds = Annotated[
    list[Any],
    WithJsonSchema(
        {
            "type": "array",
            "minItems": 1,
            "maxItems": 50,
            "items": {
                "type": "integer",
                "minimum": 1,
            },
        }
    ),
    Field(description="Non-empty list of positive integer student IDs."),
]
_UNSET = object()


def register_student_tools(mcp: Any, *, service_factory: ToolServiceFactory) -> None:
    """Register all MCP student tools against the provided server."""

    def execute_tool(
        tool_name: str,
        operation: Callable[[], dict[str, Any]],
        *,
        result_formatter: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        logger.info("MCP tool start: %s", tool_name)
        try:
            result = operation()
            payload = result_formatter(result) if result_formatter else mcp_success(data=result)
            logger.info("MCP tool success: %s", tool_name)
            return payload
        except Exception as error:  # noqa: BLE001 - unified MCP error mapping
            payload = mcp_result_from_exception(error)
            error_code = payload["error"]["code"] if payload["error"] else "unknown"
            logger.info("MCP tool failure: %s (%s)", tool_name, error_code)
            return payload

    @mcp.tool(
        name="list_students",
        description=(
            "List students with optional keyword filtering, pagination, and safe sorting. "
            "Returns the current page of student records plus pagination metadata."
        ),
        structured_output=True,
    )
    def list_students(
        keyword: Annotated[str, Field(description="Optional keyword filter.", default="")] = "",
        page: Annotated[int, Field(description="1-based page number.", ge=1)] = 1,
        page_size: Annotated[int, Field(description="Page size from 1 to 50.", ge=1, le=50)] = 15,
        sort_by: Annotated[SortBy, Field(description="Approved sort field.")] = "student_number",
        sort_order: Annotated[SortOrder, Field(description="Sort direction.")] = "asc",
    ) -> dict[str, Any]:
        return execute_tool(
            "list_students",
            lambda: service_factory().list_students(
                keyword=keyword,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            ),
            result_formatter=lambda result: mcp_paginated(
                result["items"],
                total=result["total"],
                page=result["page"],
                page_size=result["page_size"],
                extra_meta={
                    "sort_by": result["sort_by"],
                    "sort_order": result["sort_order"],
                },
            ),
        )

    @mcp.tool(
        name="search_students",
        description=(
            "Search students by a required keyword across student_number, name, major, phone, "
            "and email while preserving the same paging and sorting rules as list_students."
        ),
        structured_output=True,
    )
    def search_students(
        keyword: Annotated[str, Field(description="Required nonblank keyword.", min_length=1)],
        page: Annotated[int, Field(description="1-based page number.", ge=1)] = 1,
        page_size: Annotated[int, Field(description="Page size from 1 to 50.", ge=1, le=50)] = 15,
        sort_by: Annotated[SortBy, Field(description="Approved sort field.")] = "student_number",
        sort_order: Annotated[SortOrder, Field(description="Sort direction.")] = "asc",
    ) -> dict[str, Any]:
        return execute_tool(
            "search_students",
            lambda: service_factory().search_students(
                keyword=keyword,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            ),
            result_formatter=lambda result: mcp_paginated(
                result["items"],
                total=result["total"],
                page=result["page"],
                page_size=result["page_size"],
                extra_meta={
                    "sort_by": result["sort_by"],
                    "sort_order": result["sort_order"],
                },
            ),
        )

    @mcp.tool(
        name="get_student_by_id",
        description="Retrieve one student by positive integer ID.",
        structured_output=True,
    )
    def get_student_by_id(
        student_id: PositiveStudentId,
    ) -> dict[str, Any]:
        return execute_tool(
            "get_student_by_id",
            lambda: service_factory().get_student_by_id(student_id),
        )

    @mcp.tool(
        name="get_student_by_number",
        description=(
            "Retrieve one student by student_number. Student numbers stay as text and preserve "
            "leading zeros."
        ),
        structured_output=True,
    )
    def get_student_by_number(
        student_number: Annotated[str, Field(description="Nonblank student number.", min_length=1)],
    ) -> dict[str, Any]:
        return execute_tool(
            "get_student_by_number",
            lambda: service_factory().get_student_by_number(student_number),
        )

    @mcp.tool(
        name="count_students",
        description=(
            "Count students in SQLite using the approved keyword search predicate. An empty "
            "keyword counts all students."
        ),
        structured_output=True,
    )
    def count_students(
        keyword: Annotated[str, Field(description="Optional keyword filter.", default="")] = "",
    ) -> dict[str, Any]:
        return execute_tool(
            "count_students",
            lambda: service_factory().count_students(keyword=keyword),
        )

    @mcp.tool(
        name="add_student",
        description="Create one student using the approved student field contract and validation rules.",
        structured_output=True,
    )
    def add_student(
        student_number: Annotated[str, Field(description="Required student number.", min_length=1)],
        name: Annotated[str, Field(description="Required student name.", min_length=1)],
        gender: Annotated[str | None, Field(description="Optional gender.")] = None,
        age: Annotated[int | None, Field(description="Optional age from 10 to 100.", ge=10, le=100)] = None,
        major: Annotated[str | None, Field(description="Optional major.")] = None,
        year_level: Annotated[YearLevel | None, Field(description="Optional academic year level.")] = None,
        score: Annotated[int | None, Field(description="Optional academic score from 0 to 100.", ge=0, le=100)] = None,
        phone: Annotated[str | None, Field(description="Optional phone number.")] = None,
        email: Annotated[str | None, Field(description="Optional email address.")] = None,
    ) -> dict[str, Any]:
        return execute_tool(
            "add_student",
            lambda: service_factory().create_student(
                {
                    "student_number": student_number,
                    "name": name,
                    "gender": gender,
                    "age": age,
                    "major": major,
                    "year_level": year_level,
                    "score": score,
                    "phone": phone,
                    "email": email,
                }
            ),
            result_formatter=lambda result: mcp_success(
                data=result,
                message="Student created successfully",
            ),
        )

    @mcp.tool(
        name="update_student",
        description=(
            "Update one student by ID using one or more editable fields. Protected fields such as "
            "id, created_at, and updated_at cannot be changed."
        ),
        structured_output=True,
    )
    def update_student(
        student_id: PositiveStudentId,
        student_number: Annotated[str | None, Field(description="Optional updated student number.")] = _UNSET,
        name: Annotated[str | None, Field(description="Optional updated name.")] = _UNSET,
        gender: Annotated[str | None, Field(description="Optional updated gender.")] = _UNSET,
        age: Annotated[int | None, Field(description="Optional updated age from 10 to 100.", ge=10, le=100)] = _UNSET,
        major: Annotated[str | None, Field(description="Optional updated major.")] = _UNSET,
        year_level: Annotated[YearLevel | None, Field(description="Optional updated academic year level.")] = _UNSET,
        score: Annotated[int | None, Field(description="Optional updated score from 0 to 100.", ge=0, le=100)] = _UNSET,
        phone: Annotated[str | None, Field(description="Optional updated phone number.")] = _UNSET,
        email: Annotated[str | None, Field(description="Optional updated email address.")] = _UNSET,
    ) -> dict[str, Any]:
        payload = {
            field: value
            for field, value in {
                "student_number": student_number,
                "name": name,
                "gender": gender,
                "age": age,
                "major": major,
                "year_level": year_level,
                "score": score,
                "phone": phone,
                "email": email,
            }.items()
            if value is not _UNSET
        }
        return execute_tool(
            "update_student",
            lambda: service_factory().update_student(student_id, payload),
            result_formatter=lambda result: mcp_success(
                data=result,
                message="Student updated successfully",
            ),
        )

    @mcp.tool(
        name="upsert_student",
        description=(
            "Create a student when the provided student_number does not exist, or update the "
            "matching student when it already exists."
        ),
        structured_output=True,
    )
    def upsert_student(
        student_number: Annotated[str, Field(description="Required student number identity key.", min_length=1)],
        name: Annotated[str, Field(description="Required student name.", min_length=1)],
        gender: Annotated[str | None, Field(description="Optional gender.")] = None,
        age: Annotated[int | None, Field(description="Optional age from 10 to 100.", ge=10, le=100)] = None,
        major: Annotated[str | None, Field(description="Optional major.")] = None,
        year_level: Annotated[YearLevel | None, Field(description="Optional academic year level.")] = None,
        score: Annotated[int | None, Field(description="Optional academic score from 0 to 100.", ge=0, le=100)] = None,
        phone: Annotated[str | None, Field(description="Optional phone number.")] = None,
        email: Annotated[str | None, Field(description="Optional email address.")] = None,
    ) -> dict[str, Any]:
        return execute_tool(
            "upsert_student",
            lambda: service_factory().upsert_student(
                {
                    "student_number": student_number,
                    "name": name,
                    "gender": gender,
                    "age": age,
                    "major": major,
                    "year_level": year_level,
                    "score": score,
                    "phone": phone,
                    "email": email,
                }
            ),
            result_formatter=lambda result: mcp_success(
                data=result,
                message="Student upsert completed",
            ),
        )

    @mcp.tool(
        name="delete_student",
        description="Delete one student by positive integer ID.",
        structured_output=True,
    )
    def delete_student(
        student_id: PositiveStudentId,
    ) -> dict[str, Any]:
        return execute_tool(
            "delete_student",
            lambda: service_factory().delete_student(student_id),
            result_formatter=lambda result: mcp_success(
                data=result,
                message="Student deleted successfully",
            ),
        )

    @mcp.tool(
        name="batch_delete_students",
        description=(
            "Delete multiple students in one request using a non-empty list of positive integer IDs. "
            "Duplicate IDs are normalized before deletion."
        ),
        structured_output=True,
    )
    def batch_delete_students(
        student_ids: BatchDeleteStudentIds,
    ) -> dict[str, Any]:
        return execute_tool(
            "batch_delete_students",
            lambda: service_factory().batch_delete_students({"student_ids": student_ids}),
            result_formatter=lambda result: mcp_success(
                data=result,
                message="Students deleted successfully",
            ),
        )
