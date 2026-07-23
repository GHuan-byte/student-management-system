"""Framework-independent student service construction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.config import create_config
from app.database.connection import create_connection_factory
from app.repositories.student_repository import StudentRepository
from app.services.student_service import StudentService


def project_root() -> Path:
    """Return the project root for the current repository."""
    return Path(__file__).resolve().parents[2]


def build_runtime_config(
    config_name: str | None = None,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_env: bool = True,
) -> dict[str, Any]:
    """Build the runtime configuration mapping without creating a Flask app."""
    resolved_project_root = project_root()
    if load_env:
        load_dotenv(resolved_project_root / ".env", override=False)

    config = create_config(config_name)
    runtime_config = config.to_mapping()
    runtime_config["PROJECT_ROOT"] = str(resolved_project_root)

    if config_overrides:
        runtime_config.update(config_overrides)

    config.finalize(
        runtime_config,
        project_root=resolved_project_root,
        instance_path=resolved_project_root / "instance",
    )
    return runtime_config


def create_student_service_from_database_path(database_path: str | Path) -> StudentService:
    """Create a student service for the provided database path."""
    connection_factory = create_connection_factory(database_path)
    repository = StudentRepository(
        database_path=database_path,
        connection_factory=connection_factory,
    )
    return StudentService(repository)


def create_student_service_from_config(
    config_name: str | None = None,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_env: bool = True,
) -> StudentService:
    """Create a student service using the project's runtime config rules."""
    runtime_config = build_runtime_config(
        config_name,
        config_overrides=config_overrides,
        load_env=load_env,
    )
    return create_student_service_from_database_path(runtime_config["DATABASE_PATH"])
