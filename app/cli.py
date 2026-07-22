"""Flask CLI commands for project maintenance tasks."""

from __future__ import annotations

from pathlib import Path

import click
from flask import Flask, current_app

from app.database.schema import initialize_database


def register_cli_commands(app: Flask) -> None:
    """Register CLI commands used by the application."""

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Initialize the configured SQLite database schema."""
        database_path = Path(current_app.config["DATABASE_PATH"])
        database_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_database(database_path)
        click.echo(f"Initialized database at {database_path}")
