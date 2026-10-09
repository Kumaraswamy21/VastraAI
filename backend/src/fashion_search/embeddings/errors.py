"""Backward-compatible embedding aliases for provider-neutral errors."""

from fashion_search.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderError,
    AIProviderResponseError,
    AIProviderUnavailableError,
    EmbeddingDimensionError,
)


class EmbeddingError(AIProviderError):
    """Base embedding failure."""


class EmbeddingConfigError(AIProviderAuthenticationError, EmbeddingError):
    """Invalid configuration or credentials. Do not retry."""


class EmbeddingValidationError(EmbeddingDimensionError, EmbeddingError):
    """Invalid input or response. Do not retry."""


class EmbeddingTransientError(AIProviderUnavailableError, EmbeddingError):
    """Rate limit, timeout, or temporary provider failure. Safe to retry."""
