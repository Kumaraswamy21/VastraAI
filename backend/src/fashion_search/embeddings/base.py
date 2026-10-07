"""Provider interface for text embeddings."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Encode catalog text and queries into dense vectors."""

    name: str

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of strings in stable input order."""
        ...
