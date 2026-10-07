"""Gemini embedding provider (optional alternative to local models)."""

from fashion_search.embeddings.base import EmbeddingProvider


class GeminiEmbedder:
    """Remote Gemini embeddings. Satisfies `EmbeddingProvider`."""

    name = "gemini"

    def embed_text(self, text: str) -> list[float]:
        """Embed one string via Gemini."""
        raise NotImplementedError("Gemini embeddings are scheduled for Day 3.")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings via Gemini."""
        raise NotImplementedError("Gemini embeddings are scheduled for Day 3.")


def build_gemini_embedder() -> EmbeddingProvider:
    """Factory for the Gemini embedding provider."""
    return GeminiEmbedder()
