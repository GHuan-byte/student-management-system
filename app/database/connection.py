"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable


ConnectionFactory = Callable[[], sqlite3.Connection]


def open_connection(database_path: str | Path) -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_connection_factory(database_path: str | Path) -> ConnectionFactory:
    """Create a reusable connection factory for the given database path."""
    resolved_path = Path(database_path)

    def factory() -> sqlite3.Connection:
        return open_connection(resolved_path)

    return factory
