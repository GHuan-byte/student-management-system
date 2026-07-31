"""Flask application factory for the Foundation phase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask

from app.auth import initialize_auth_storage_and_bootstrap, register_auth
from app.cli import register_cli_commands
from app.config import _is_secret_key_safe, create_config
from app.error_handlers import register_error_handlers
from app.logging_config import configure_logging
from app.services.factory import create_student_service_from_database_path
from app.services.student_service import StudentService


def register_blueprints(app: Flask) -> None:
    """Register Flask blueprints through a single integration point."""
    from app.routes.health import health_bp
    from app.routes.auth import auth_bp
    from app.routes.chat import chat_bp
    from app.routes.pages import pages_bp
    from app.routes.students import students_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(students_bp)


def create_student_service(app: Flask) -> StudentService:
    """Create a student service from configured application dependencies."""
    return create_student_service_from_database_path(app.config["DATABASE_PATH"])


def create_ai_chat_service(app: Flask):
    """Build a request-scoped AI chat service from server-side config."""
    from app.services.ai_action_confirmation import AIActionConfirmation
    from app.services.ai_chat_service import AIChatService
    from app.services.deepseek_client import DeepSeekClient
    from app.services.mcp_tool_adapter import MCPToolAdapter

    confirmation = None
    if app.config["AI_WRITE_CONFIRMATION"]:
        confirmation = app.extensions["ai_action_confirmation"]
    return AIChatService(
        deepseek_client_factory=lambda: DeepSeekClient(app.config),
        mcp_adapter_factory=lambda: MCPToolAdapter(
            database_path=app.config["DATABASE_PATH"],
        ),
        action_confirmation=confirmation,
        max_tool_rounds=app.config["AI_MAX_TOOL_ROUNDS"],
        ai_configured=app.config["AI_CONFIGURED"],
    )


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
        if "SECRET_KEY" in config_overrides and "AI_WRITE_CONFIRMATION" not in config_overrides:
            app.config["AI_WRITE_CONFIRMATION"] = _is_secret_key_safe(app.config["SECRET_KEY"])

    config.finalize(
        app.config,
        project_root=project_root,
        instance_path=Path(app.instance_path),
    )
    configure_logging(app)
    initialize_auth_storage_and_bootstrap(app)
    app.extensions["user_service_factory"] = lambda: __import__(
        "app.auth", fromlist=["create_user_service"]
    ).create_user_service(app.config["DATABASE_PATH"])
    app.extensions["student_service_factory"] = lambda: create_student_service(app)
    if app.config["AI_WRITE_CONFIRMATION"]:
        from app.services.ai_action_confirmation import AIActionConfirmation

        app.extensions["ai_action_confirmation"] = AIActionConfirmation(
            secret_key=app.config["SECRET_KEY"],
            token_ttl_seconds=app.config["AI_CONFIRMATION_TOKEN_TTL_SECONDS"] or 120,
        )
    app.extensions["ai_chat_service_factory"] = lambda: create_ai_chat_service(app)
    register_error_handlers(app)
    register_auth(app)
    register_cli_commands(app)
    register_blueprints(app)
    return app


def app_root() -> str:
    """Return the package root path."""
    return str(Path(__file__).resolve().parent)
