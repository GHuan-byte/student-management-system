"""SQLite schema initialization for student CRUD."""

from __future__ import annotations

from pathlib import Path

from app.database.connection import create_connection_factory

YEAR_LEVEL_VALUES = (
    "\u5927\u4e00",
    "\u5927\u4e8c",
    "\u5927\u4e09",
    "\u5927\u56db",
)

CREATE_STUDENTS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_number TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    gender TEXT,
    age INTEGER,
    major TEXT,
    year_level TEXT,
    score INTEGER,
    phone TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (age IS NULL OR age BETWEEN 10 AND 100),
    CHECK (score IS NULL OR score BETWEEN 0 AND 100),
    CHECK (year_level IS NULL OR year_level IN {YEAR_LEVEL_VALUES})
)
"""

CREATE_USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('viewer', 'staff', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    auth_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
)
"""


def initialize_database(database_path: str | Path) -> None:
    """Create required tables without deleting existing data."""
    connection_factory = create_connection_factory(database_path)
    connection = connection_factory()
    try:
        with connection:
            connection.execute(CREATE_STUDENTS_TABLE_SQL)
            connection.execute(CREATE_USERS_TABLE_SQL)
    finally:
        connection.close()
