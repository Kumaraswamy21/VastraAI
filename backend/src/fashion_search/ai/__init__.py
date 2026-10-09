"""Provider-neutral AI contracts, errors, and composition helpers."""

from fashion_search.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    EmbeddingCompatibilityError,
    EmbeddingDimensionError,
)

__all__ = [
    "AIProviderError",
    "AIProviderAuthenticationError",
    "AIProviderRateLimitError",
    "AIProviderResponseError",
    "AIProviderTimeoutError",
    "AIProviderUnavailableError",
    "EmbeddingCompatibilityError",
    "EmbeddingDimensionError",
]
