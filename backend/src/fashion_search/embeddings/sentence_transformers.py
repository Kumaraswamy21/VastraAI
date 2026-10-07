"""Local Sentence Transformers embedding provider.

Day 3 will load `EMBEDDING_MODEL` from disk or Hugging Face cache.
"""

from fashion_search.embeddings.base import EmbeddingProvider


class SentenceTransformerEmbedder:
    """On-device embeddings. Satisfies `EmbeddingProvider`."""

    name = "sentence_transformers"

    def embed_text(self, text: str) -> list[float]:
        """Embed one string using the local encoder."""
        raise NotImplementedError("Local embeddings are scheduled for Day 3.")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings using the local encoder."""
        raise NotImplementedError("Local embeddings are scheduled for Day 3.")


def build_sentence_transformer_embedder() -> EmbeddingProvider:
    """Factory for the default local embedding provider."""
    return SentenceTransformerEmbedder()
