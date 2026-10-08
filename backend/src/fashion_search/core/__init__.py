"""Shared utilities: logging, database ping, and domain errors."""

from fashion_search.core.db import get_engine, ping_database
from fashion_search.core.exceptions import AmbiguousQueryError, OffTopicQueryError
from fashion_search.core.logging import configure_logging, get_logger

__all__ = [
    "AmbiguousQueryError",
    "OffTopicQueryError",
    "configure_logging",
    "get_engine",
    "get_logger",
    "ping_database",
]
