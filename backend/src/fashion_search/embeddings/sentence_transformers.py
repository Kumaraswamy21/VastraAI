"""Local Sentence Transformers provider (disabled).

This project uses Google Gemini embeddings exclusively. Local models are
not installed or executed.
"""

from fashion_search.embeddings.errors import EmbeddingConfigError


class SentenceTransformerEmbedder:
    """Placeholder kept for import compatibility; always raises."""

    name = "sentence_transformers"

    def embed_text(self, text: str) -> list[float]:
        raise EmbeddingConfigError(
            "Local Sentence Transformers embeddings are disabled; use Gemini"
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingConfigError(
            "Local Sentence Transformers embeddings are disabled; use Gemini"
        )


def build_sentence_transformer_embedder() -> SentenceTransformerEmbedder:
    """Factory that returns a disabled local embedder."""
    return SentenceTransformerEmbedder()
