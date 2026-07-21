"""Logging configuration for the Foundation phase."""

from __future__ import annotations

import logging
import logging.config

from flask import Flask


def configure_logging(app: Flask) -> None:
    """Configure application-managed logging."""
    level = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )
    app.logger.setLevel(level)
