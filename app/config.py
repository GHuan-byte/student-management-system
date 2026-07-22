"""Configuration objects for the Foundation phase."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEV_SECRET_KEY = "dev-secret-change-in-production"
DEFAULT_DATABASE_NAME = "students_v2.db"


@dataclass
class Config:
    """Base configuration."""

    debug: bool = False
    testing: bool = False

    def to_mapping(self) -> dict[str, Any]:
        return {
            "APP_ENV": os.environ.get("APP_ENV", "development"),
            "DEBUG": self.debug,
            "TESTING": self.testing,
            "SECRET_KEY": os.environ.get("SECRET_KEY", DEV_SECRET_KEY),
            "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO").upper(),
            "DATABASE_PATH": os.environ.get("DATABASE_PATH"),
        }

    def default_database_path(self, instance_path: Path) -> Path | None:
        return instance_path / DEFAULT_DATABASE_NAME

    def finalize(
        self,
        config: dict[str, Any],
        *,
        project_root: Path,
        instance_path: Path,
    ) -> None:
        raw_database_path = config.get("DATABASE_PATH")
        database_path = raw_database_path

        if isinstance(database_path, str):
            database_path = database_path.strip() or None

        if database_path is None:
            default_path = self.default_database_path(instance_path)
            config["DATABASE_PATH"] = str(default_path) if default_path else None
        else:
            resolved_path = Path(database_path)
            if not resolved_path.is_absolute():
                resolved_path = project_root / resolved_path
            config["DATABASE_PATH"] = str(resolved_path)

        self.validate_final(config)

    def validate_final(self, config: dict[str, Any]) -> None:
        """Allow subclasses to validate finalized configuration."""


@dataclass
class DevelopmentConfig(Config):
    debug: bool = True


@dataclass
class TestingConfig(Config):
    testing: bool = True


@dataclass
class ProductionConfig(Config):
    def default_database_path(self, instance_path: Path) -> Path | None:
        return None

    def to_mapping(self) -> dict[str, Any]:
        mapping = super().to_mapping()
        mapping["APP_ENV"] = "production"
        mapping["DEBUG"] = False
        mapping["TESTING"] = False
        return mapping

    def validate_final(self, config: dict[str, Any]) -> None:
        secret_key = config.get("SECRET_KEY")
        if not secret_key or secret_key == DEV_SECRET_KEY:
            raise RuntimeError(
                "Production SECRET_KEY must be set and must not use the development default."
            )

        if not config.get("DATABASE_PATH"):
            raise RuntimeError("Production DATABASE_PATH must be configured explicitly.")


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def resolve_config_name(config_name: str | None) -> str:
    """Resolve config name from explicit input, APP_ENV, then default."""
    resolved = config_name or os.environ.get("APP_ENV") or "development"
    if resolved not in CONFIG_MAP:
        raise ValueError(f"Unknown config name: {resolved}")
    return resolved


def create_config(config_name: str | None) -> Config:
    """Instantiate the resolved configuration object."""
    resolved = resolve_config_name(config_name)
    return CONFIG_MAP[resolved]()
