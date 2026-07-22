"""Student CRUD API routes."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, request

from app.services.student_service import StudentService
from app.utils.response import api_success

students_bp = Blueprint("students", __name__)


def get_student_service() -> StudentService:
    """Resolve the configured student service from the Flask app."""
    service_factory = current_app.extensions["student_service_factory"]
    return service_factory()


def get_json_payload() -> dict[str, Any] | Any:
    """Return the request JSON payload."""
    return request.get_json(silent=True)


@students_bp.get("/api/students")
def list_students():
    service = get_student_service()
    keyword = request.args.get("keyword")
    students = service.list_students(keyword=keyword)
    return api_success(data=students)


@students_bp.get("/api/students/<int:student_id>")
def get_student(student_id: int):
    service = get_student_service()
    student = service.get_student_by_id(student_id)
    return api_success(data=student)


@students_bp.post("/api/students")
def create_student():
    service = get_student_service()
    student = service.create_student(get_json_payload())
    return api_success(
        data=student,
        message="Student created successfully",
        status_code=201,
    )


@students_bp.put("/api/students/<int:student_id>")
def update_student(student_id: int):
    service = get_student_service()
    student = service.update_student(student_id, get_json_payload())
    return api_success(data=student, message="Student updated successfully")


@students_bp.delete("/api/students/<int:student_id>")
def delete_student(student_id: int):
    service = get_student_service()
    student = service.delete_student(student_id)
    return api_success(data=student, message="Student deleted successfully")
