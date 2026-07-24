"""Configuration objects for the Foundation phase."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEV_SECRET_KEY = "dev-secret-change-in-production"
PLACEHOLDER_SECRET_KEY = "replace-with-development-secret"
DEFAULT_DATABASE_NAME = "students_v2.db"

# ---------------------------------------------------------------------------
# AI Chat environment variable names
# ---------------------------------------------------------------------------

DEEPSEEK_REQUIRED_VARS = ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE", "DEEPSEEK_MODEL")

AI_STRING_VARS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_BASE",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_REASONING_EFFORT",
)

AI_INT_VARS = (
    "DEEPSEEK_TIMEOUT_SECONDS",
    "DEEPSEEK_MAX_OUTPUT_TOKENS",
    "AI_MAX_TOOL_ROUNDS",
    "AI_MAX_HISTORY_MESSAGES",
    "AI_MAX_MESSAGE_LENGTH",
    "AI_CONFIRMATION_TOKEN_TTL_SECONDS",
)

AI_BOOL_VARS = (
    "DEEPSEEK_THINKING",
    "DEEPSEEK_TRUST_ENV",
)

ALLOWED_REASONING_EFFORTS = frozenset({"high", "max"})


# ---------------------------------------------------------------------------
# AI env‑var parsing helpers
# ---------------------------------------------------------------------------


def _parse_int_env(key: str) -> int | None:
    """Read an integer from the environment; return None if missing/invalid."""
    raw = os.environ.get(key)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _parse_bool_env(key: str) -> bool:
    """Read a boolean from the environment (case‑insensitive)."""
    raw = os.environ.get(key)
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


INSECURE_SECRET_KEYS = frozenset({
    DEV_SECRET_KEY,
    PLACEHOLDER_SECRET_KEY,
})


def _is_secret_key_safe(secret_key: str | None) -> bool:
    """Return True when SECRET_KEY is set to a non‑development value."""
    if not secret_key:
        return False
    return secret_key not in INSECURE_SECRET_KEYS


def _compute_ai_configured(cfg: dict[str, Any]) -> bool:
    """Determine whether AI Chat is fully configured.

    Requires:
    - All ``DEEPSEEK_REQUIRED_VARS`` set truthy.
    - If ``DEEPSEEK_THINKING`` is enabled, ``DEEPSEEK_REASONING_EFFORT``
      must be one of ``ALLOWED_REASONING_EFFORTS``.
    """
    if not all(cfg.get(var) for var in DEEPSEEK_REQUIRED_VARS):
        return False

    if cfg.get("DEEPSEEK_THINKING"):
        effort = cfg.get("DEEPSEEK_REASONING_EFFORT")
        if not effort or effort not in ALLOWED_REASONING_EFFORTS:
            return False

    return True


def _build_ai_config() -> dict[str, Any]:
    """Read all AI‑related configuration from the environment.

    No hardcoded fallback for API key, API base, or model.
    """
    cfg: dict[str, Any] = {}

    for var in AI_STRING_VARS:
        cfg[var] = os.environ.get(var) or None

    for var in AI_INT_VARS:
        cfg[var] = _parse_int_env(var)

    for var in AI_BOOL_VARS:
        cfg[var] = _parse_bool_env(var)

    # AI_CONFIGURED is True only when all required DeepSeek vars are set
    # When thinking is enabled, reasoning_effort must also be valid.
    cfg["AI_CONFIGURED"] = _compute_ai_configured(cfg)

    # AI_WRITE_CONFIRMATION depends only on SECRET_KEY safety
    raw_secret = os.environ.get("SECRET_KEY")
    cfg["AI_WRITE_CONFIRMATION"] = _is_secret_key_safe(raw_secret)

    return cfg


# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Base configuration."""

    debug: bool = False
    testing: bool = False

    def to_mapping(self) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            "APP_ENV": os.environ.get("APP_ENV", "development"),
            "DEBUG": self.debug,
            "TESTING": self.testing,
            "SECRET_KEY": os.environ.get("SECRET_KEY", DEV_SECRET_KEY),
            "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO").upper(),
            "DATABASE_PATH": os.environ.get("DATABASE_PATH"),
        }
        mapping.update(_build_ai_config())
        return mapping

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
