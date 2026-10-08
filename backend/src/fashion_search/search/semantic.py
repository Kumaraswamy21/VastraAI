"""Orchestrate Gemini query embedding + pgvector cosine search."""

from __future__ import annotations

import time

from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.embeddings.errors import (
    EmbeddingConfigError,
    EmbeddingTransientError,
    EmbeddingValidationError,
)
from fashion_search.embeddings.gemini import GeminiEmbedder, build_gemini_embedder
from fashion_search.search.schemas import (
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from fashion_search.search.vector import VectorHit, search_by_vector

logger = get_logger(__name__)


class SemanticSearchError(Exception):
    """Semantic search failed for a mapped HTTP status."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def normalize_query(query: str) -> str:
    """Strip and validate a user search query."""
    cleaned = (query or "").strip()
    if not cleaned:
        raise SemanticSearchError("query must not be empty", status_code=422)
    return cleaned


def hit_from_row(hit: VectorHit) -> SemanticSearchHit:
    """Map a repository hit to the public API shape (no embedding vectors)."""
    product = hit.product
    return SemanticSearchHit(
        product_id=product.id,
        title=product.title,
        category=product.category,
        color=product.color,
        material=product.material,
        style=product.style,
        gender=product.gender,
        occasion=product.occasion,
        price_inr=product.price_inr,
        currency="INR",
        image_reference=product.image_reference,
        product_url=f"/products/{product.slug}",
        similarity_score=round(hit.similarity_score, 6),
    )


def semantic_search(
    request: SemanticSearchRequest,
    *,
    settings: Settings | None = None,
    embedder: GeminiEmbedder | None = None,
) -> SemanticSearchResponse:
    """Embed the query with Gemini and rank products by cosine similarity."""
    cfg = settings or get_settings()
    query = normalize_query(request.query)
    worker = embedder or build_gemini_embedder(cfg)

    started = time.perf_counter()
    try:
        embed_started = time.perf_counter()
        query_vector = worker.embed_query(query)
        embed_ms = (time.perf_counter() - embed_started) * 1000
    except EmbeddingValidationError as exc:
        raise SemanticSearchError(str(exc), status_code=422) from exc
    except EmbeddingConfigError as exc:
        raise SemanticSearchError(str(exc), status_code=502) from exc
    except EmbeddingTransientError as exc:
        raise SemanticSearchError(str(exc), status_code=503) from exc

    db_started = time.perf_counter()
    try:
        hits = search_by_vector(query_vector, limit=request.limit, settings=cfg)
    except ValueError as exc:
        raise SemanticSearchError(str(exc), status_code=422) from exc
    except Exception as exc:
        logger.exception("semantic_search_db_failed")
        raise SemanticSearchError("database search failed", status_code=503) from exc
    db_ms = (time.perf_counter() - db_started) * 1000
    total_ms = (time.perf_counter() - started) * 1000

    logger.info(
        "semantic_search query_len=%s limit=%s hits=%s embed_ms=%.1f db_ms=%.1f total_ms=%.1f",
        len(query),
        request.limit,
        len(hits),
        embed_ms,
        db_ms,
        total_ms,
    )
    return SemanticSearchResponse(
        query=query,
        total=len(hits),
        embedding_model=cfg.embedding_model,
        embedding_dimensions=cfg.embedding_dimensions,
        results=[hit_from_row(hit) for hit in hits],
    )
