"""Provider-neutral interface and validation for text embeddings."""

import asyncio
import math
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from fashion_search.ai.errors import EmbeddingDimensionError


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Encode catalog text and queries into dense vectors."""

    name: str
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document text in stable input order."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a query in the same vector space as documents."""
        ...

    def health(self) -> dict[str, object]: ...

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def aembed_query(self, text: str) -> list[float]: ...


class AsyncEmbeddingMixin:
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


def require_nonempty(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise EmbeddingDimensionError("embedding input text is empty")
    return cleaned


def validate_embedding(
    vector: Sequence[float], expected_dimensions: int
) -> list[float]:
    """Validate and L2-normalize a provider vector."""
    if not vector:
        raise EmbeddingDimensionError("embedding vector is empty")
    if len(vector) != expected_dimensions:
        raise EmbeddingDimensionError(
            f"expected {expected_dimensions} dimensions, got {len(vector)}"
        )
    values = [float(value) for value in vector]
    if any(not math.isfinite(value) for value in values):
        raise EmbeddingDimensionError("embedding contains non-finite values")
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        raise EmbeddingDimensionError("embedding vector has zero norm")
    return [value / norm for value in values]
