"""Provider-neutral product embedding contracts and adapters."""

from fashion_search.embeddings.base import EmbeddingProvider
from fashion_search.embeddings.gemini import GeminiEmbedder, build_gemini_embedder
from fashion_search.embeddings.normalize import normalize_product_text, text_hash

__all__ = [
    "EmbeddingProvider",
    "GeminiEmbedder",
    "build_gemini_embedder",
    "normalize_product_text",
    "text_hash",
]
