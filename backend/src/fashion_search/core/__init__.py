"""Shared utilities: logging and domain errors."""

from fashion_search.core.exceptions import AmbiguousQueryError, OffTopicQueryError
from fashion_search.core.logging import configure_logging, get_logger

__all__ = [
    "AmbiguousQueryError",
    "OffTopicQueryError",
    "configure_logging",
    "get_logger",
]
