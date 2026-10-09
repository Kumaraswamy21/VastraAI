"""Hybrid orchestration: constraints, semantic + keyword retrieval, RRF fusion."""

from __future__ import annotations

import time
from typing import Any

from fashion_search.catalog.models import Product
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.embeddings.errors import (
    EmbeddingConfigError,
    EmbeddingTransientError,
    EmbeddingValidationError,
)
from fashion_search.embeddings.gemini import GeminiEmbedder, build_gemini_embedder
from fashion_search.search.constraints import parse_constraints
from fashion_search.search.filters import constraints_currency_supported
from fashion_search.search.keyword import KeywordHit, search_by_keyword
from fashion_search.search.preprocess import build_retrieval_query
from fashion_search.search.ranking import RankedCandidate, reciprocal_rank_fusion
from fashion_search.search.schemas import (
    FashionSearchConstraints,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
    HybridSearchScores,
)
from fashion_search.search.semantic import SemanticSearchError, normalize_query
from fashion_search.search.vector import VectorHit, search_by_vector

logger = get_logger(__name__)


class HybridSearchError(Exception):
    """Hybrid search failed for a mapped HTTP status."""

    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


def constraints_to_filters(constraints: FashionSearchConstraints) -> dict[str, Any]:
    """Expose non-null constraint fields in API responses."""
    payload = constraints.model_dump(exclude_none=True)
    if "price_min" in payload:
        payload["price_min"] = float(payload["price_min"])
    if "price_max" in payload:
        payload["price_max"] = float(payload["price_max"])
    return payload


def _empty_response(
    query: str,
    constraints: FashionSearchConstraints,
    *,
    retrieval_query: str,
    parse_ms: float,
) -> HybridSearchResponse:
    return HybridSearchResponse(
        query=query,
        retrieval_query=retrieval_query,
        filters=constraints_to_filters(constraints),
        total=0,
        results=[],
        metrics={
            "parse_ms": round(parse_ms, 1),
            "semantic_candidates": 0,
            "keyword_candidates": 0,
            "fallback": None,
        },
    )


def _result_from_product(
    product: Product,
    ranked: RankedCandidate,
) -> HybridSearchResult:
    return HybridSearchResult(
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
        scores=HybridSearchScores(
            semantic_similarity=ranked.semantic_similarity,
            keyword_rank_score=ranked.keyword_rank_score,
            semantic_rank=ranked.semantic_rank,
            keyword_rank=ranked.keyword_rank,
            hybrid_score=round(ranked.hybrid_score, 6),
        ),
    )


def hybrid_search(
    request: HybridSearchRequest,
    *,
    settings: Settings | None = None,
    embedder: GeminiEmbedder | None = None,
    constraint_client: Any | None = None,
) -> HybridSearchResponse:
    """Parse constraints, retrieve, fuse with RRF, and return ranked products."""
    cfg = settings or get_settings()
    try:
        query = normalize_query(request.query)
    except SemanticSearchError as exc:
        raise HybridSearchError(str(exc), status_code=exc.status_code) from exc
    started = time.perf_counter()

    parse_started = time.perf_counter()
    parsed = parse_constraints(query, settings=cfg, client=constraint_client)
    constraints = parsed.constraints
    retrieval_query = build_retrieval_query(query, constraints)
    parse_ms = (time.perf_counter() - parse_started) * 1000

    if not constraints_currency_supported(constraints, settings=cfg):
        logger.info("hybrid_search unsupported_currency currency=%s", constraints.currency)
        return _empty_response(query, constraints, retrieval_query=retrieval_query, parse_ms=parse_ms)

    candidate_limit = max(request.limit, cfg.hybrid_candidate_limit)
    semantic_hits: list[VectorHit] = []
    keyword_hits: list[KeywordHit] = []
    semantic_error: str | None = None
    keyword_error: str | None = None
    embed_ms = 0.0
    semantic_ms = 0.0
    keyword_ms = 0.0

    embed_started = time.perf_counter()
    worker = embedder or build_gemini_embedder(cfg)
    try:
        query_vector = worker.embed_query(retrieval_query)
        embed_ms = (time.perf_counter() - embed_started) * 1000
        sem_started = time.perf_counter()
        semantic_hits = search_by_vector(
            query_vector,
            limit=candidate_limit,
            constraints=constraints,
            settings=cfg,
        )
        semantic_ms = (time.perf_counter() - sem_started) * 1000
    except EmbeddingValidationError as exc:
        semantic_error = str(exc)
    except (EmbeddingConfigError, EmbeddingTransientError) as exc:
        semantic_error = str(exc)
    except Exception:
        logger.exception("hybrid_semantic_path_failed")
        semantic_error = "semantic retrieval failed"

    key_started = time.perf_counter()
    try:
        keyword_hits = search_by_keyword(
            retrieval_query,
            constraints=constraints,
            limit=candidate_limit,
        )
        keyword_ms = (time.perf_counter() - key_started) * 1000
    except Exception:
        logger.exception("hybrid_keyword_failed")
        keyword_error = "keyword retrieval failed"
        keyword_ms = 0.0

    if semantic_error and keyword_error:
        if isinstance(semantic_error, str) and "empty" in semantic_error.lower():
            raise HybridSearchError(semantic_error, status_code=422)
        raise HybridSearchError(
            "semantic and keyword retrieval failed",
            status_code=503,
        )

    fallback: str | None = None
    if semantic_error and not keyword_error:
        fallback = "keyword_only"
    elif keyword_error and not semantic_error:
        fallback = "semantic_only"

    fusion_started = time.perf_counter()
    semantic_pairs = [(hit.product.id, hit.similarity_score) for hit in semantic_hits]
    keyword_pairs = [(hit.product.id, hit.rank_score) for hit in keyword_hits]
    fused = reciprocal_rank_fusion(
        semantic_pairs,
        keyword_pairs,
        rrf_k=cfg.hybrid_rrf_k,
        semantic_weight=cfg.hybrid_semantic_weight,
        keyword_weight=cfg.hybrid_keyword_weight,
    )
    fused = fused[: request.limit]
    fusion_ms = (time.perf_counter() - fusion_started) * 1000

    products_by_id: dict[int, Product] = {
        hit.product.id: hit.product for hit in semantic_hits
    }
    for hit in keyword_hits:
        products_by_id.setdefault(hit.product.id, hit.product)

    results = [
        _result_from_product(products_by_id[row.product_id], row)
        for row in fused
        if row.product_id in products_by_id
    ]
    total_ms = (time.perf_counter() - started) * 1000

    logger.info(
        "hybrid_search query_len=%s retrieval_len=%s limit=%s semantic_hits=%s "
        "keyword_hits=%s returned=%s fallback=%s parse_ms=%.1f embed_ms=%.1f "
        "semantic_ms=%.1f keyword_ms=%.1f fusion_ms=%.1f total_ms=%.1f",
        len(query),
        len(retrieval_query),
        request.limit,
        len(semantic_hits),
        len(keyword_hits),
        len(results),
        fallback,
        parse_ms,
        embed_ms,
        semantic_ms,
        keyword_ms,
        fusion_ms,
        total_ms,
    )
    return HybridSearchResponse(
        query=query,
        retrieval_query=retrieval_query,
        filters=constraints_to_filters(constraints),
        total=len(results),
        results=results,
        metrics={
            "parse_ms": round(parse_ms, 1),
            "embed_ms": round(embed_ms, 1),
            "semantic_ms": round(semantic_ms, 1),
            "keyword_ms": round(keyword_ms, 1),
            "fusion_ms": round(fusion_ms, 1),
            "total_ms": round(total_ms, 1),
            "semantic_candidates": len(semantic_hits),
            "keyword_candidates": len(keyword_hits),
            "fallback": fallback,
        },
    )
