"""Server-rendered page routes."""

from __future__ import annotations

from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/students")
def students_page():
    return render_template("students.html")
