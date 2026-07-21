"""Flask application factory for the Foundation phase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask

from app.config import create_config
from app.error_handlers import register_error_handlers
from app.logging_config import configure_logging


def register_blueprints(app: Flask) -> None:
    """Register Flask blueprints through a single integration point."""
    from app.routes.health import health_bp

    app.register_blueprint(health_bp)


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
    app.config.from_mapping(config.to_mapping())

    if config_overrides:
        app.config.update(config_overrides)

    config.validate_final(app.config)
    configure_logging(app)
    register_error_handlers(app)
    register_blueprints(app)
    return app


def app_root() -> str:
    """Return the package root path."""
    return str(Path(__file__).resolve().parent)
