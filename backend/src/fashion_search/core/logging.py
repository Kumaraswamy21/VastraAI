"""Process logging helpers."""

import logging

from fashion_search.config.settings import get_settings


def configure_logging() -> None:
    """Configure root logging from settings. Safe to call more than once."""
    level_name = get_settings().log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=False,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a module."""
    return logging.getLogger(name)
