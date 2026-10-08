"""Embedding-domain errors."""


class EmbeddingError(Exception):
    """Base embedding failure."""


class EmbeddingConfigError(EmbeddingError):
    """Invalid configuration or credentials. Do not retry."""


class EmbeddingValidationError(EmbeddingError):
    """Invalid input or response. Do not retry."""


class EmbeddingTransientError(EmbeddingError):
    """Rate limit, timeout, or temporary provider failure. Safe to retry."""
