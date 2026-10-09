"""Orchestrate provider-neutral query embedding + compatible vector search."""

from __future__ import annotations

import time

from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    EmbeddingDimensionError,
)
from fashion_search.ai.factory import get_embedding_provider
from fashion_search.embeddings.base import EmbeddingProvider
from fashion_search.search.schemas import (
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from fashion_search.search.vector import VectorHit, embedding_index_status, search_by_vector

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
    embedder: EmbeddingProvider | None = None,
) -> SemanticSearchResponse:
    """Embed a query and search only the provider's matching vector space."""
    cfg = settings or get_settings()
    query = normalize_query(request.query)
    worker = embedder or get_embedding_provider(cfg)
    provider_name = (
        worker.name if isinstance(getattr(worker, "name", None), str)
        else getattr(cfg, "embedding_provider", "gemini")
    )
    model_name = (
        worker.model_name
        if isinstance(getattr(worker, "model_name", None), str)
        else getattr(cfg, "embedding_model", "gemini-embedding-001")
    )
    dimensions = (
        worker.dimensions
        if isinstance(getattr(worker, "dimensions", None), int)
        else getattr(cfg, "embedding_dimensions", 768)
    )
    index_status = "unknown"
    if embedder is None:
        try:
            index_status = embedding_index_status(
                provider=provider_name, model=model_name, dimensions=dimensions
            )
        except Exception as exc:
            logger.exception("embedding_index_status_failed provider=%s", provider_name)
            raise SemanticSearchError("embedding index status unavailable", status_code=503) from exc
        if index_status != "ready":
            raise SemanticSearchError(
                f"embedding index is {index_status}; re-embed the catalog for {provider_name}",
                status_code=409,
            )

    started = time.perf_counter()
    try:
        embed_started = time.perf_counter()
        query_vector = worker.embed_query(query)
        embed_ms = (time.perf_counter() - embed_started) * 1000
    except EmbeddingDimensionError as exc:
        raise SemanticSearchError(str(exc), status_code=422) from exc
    except AIProviderAuthenticationError as exc:
        raise SemanticSearchError(str(exc), status_code=502) from exc
    except (AIProviderTimeoutError, AIProviderUnavailableError) as exc:
        raise SemanticSearchError(str(exc), status_code=503) from exc

    db_started = time.perf_counter()
    try:
        hits = search_by_vector(
            query_vector,
            limit=request.limit,
            settings=cfg,
            provider=provider_name,
            model=model_name,
            dimensions=dimensions,
        )
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
        embedding_provider=provider_name,
        embedding_model=model_name,
        embedding_dimensions=dimensions,
        embedding_index_status=index_status,
        results=[hit_from_row(hit) for hit in hits],
    )
