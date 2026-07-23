"""Flask application factory for the Foundation phase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask

from app.cli import register_cli_commands
from app.config import create_config
from app.error_handlers import register_error_handlers
from app.logging_config import configure_logging
from app.services.factory import create_student_service_from_database_path
from app.services.student_service import StudentService


def register_blueprints(app: Flask) -> None:
    """Register Flask blueprints through a single integration point."""
    from app.routes.health import health_bp
    from app.routes.pages import pages_bp
    from app.routes.students import students_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(students_bp)


def create_student_service(app: Flask) -> StudentService:
    """Create a student service from configured application dependencies."""
    return create_student_service_from_database_path(app.config["DATABASE_PATH"])


def create_app(
    config_name: str | None = None,
    config_overrides: dict[str, Any] | None = None,
    load_env: bool = True,
) -> Flask:
    """Create and configure the Flask application."""
    if load_env:
        load_dotenv(Path(app_root()).parent / ".env", override=False)

    config = create_config(config_name)
    app = Flask(__name__)
    project_root = Path(app_root()).parent
    app.config["PROJECT_ROOT"] = str(project_root)
    app.config.from_mapping(config.to_mapping())

    if config_overrides:
        app.config.update(config_overrides)

    config.finalize(
        app.config,
        project_root=project_root,
        instance_path=Path(app.instance_path),
    )
    app.extensions["student_service_factory"] = lambda: create_student_service(app)
    configure_logging(app)
    register_error_handlers(app)
    register_cli_commands(app)
    register_blueprints(app)
    return app


def app_root() -> str:
    """Return the package root path."""
    return str(Path(__file__).resolve().parent)
