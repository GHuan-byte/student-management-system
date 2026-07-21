"""Foundation health-check route."""

from __future__ import annotations

from flask import Blueprint

from app.utils.response import api_success

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health_check():
    return api_success(data={"status": "ok"})
