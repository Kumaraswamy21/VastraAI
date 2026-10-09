"""Hybrid orchestration: constraints, semantic + keyword retrieval, RRF fusion."""

from __future__ import annotations

import time
from typing import Any

from fashion_search.catalog.models import Product
from fashion_search.ai.errors import AIProviderError, EmbeddingDimensionError
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.ai.factory import get_embedding_provider
from fashion_search.embeddings.base import EmbeddingProvider
from fashion_search.search.constraints import parse_constraints
from fashion_search.search.diagnostics import diagnose_zero_results
from fashion_search.search.explanations import (
    MatchExplanationBuilder,
    QualityThresholds,
    classify_match_quality,
    matched_constraints,
)
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
    RankingEvidence,
)
from fashion_search.search.semantic import SemanticSearchError, normalize_query
from fashion_search.search.vector import (
    VectorHit,
    embedding_index_status,
    search_by_vector,
)

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
    status: str = "no_results",
    message: str = "No products were returned for this search.",
) -> HybridSearchResponse:
    return HybridSearchResponse(
        query=query,
        retrieval_query=retrieval_query,
        filters=constraints_to_filters(constraints),
        total=0,
        results=[],
        search_status=status,
        message=message,
        metrics={
            "parse_ms": round(parse_ms, 1),
            "explanation_ms": 0.0,
            "semantic_candidates": 0,
            "keyword_candidates": 0,
            "fallback": None,
            "strong_results": 0,
            "good_results": 0,
            "weak_results": 0,
            "zero_results": 1,
        },
    )


def _result_from_product(
    product: Product,
    ranked: RankedCandidate,
    constraints: FashionSearchConstraints,
    *,
    final_rank: int,
    thresholds: QualityThresholds,
    builder: MatchExplanationBuilder,
) -> HybridSearchResult:
    quality = classify_match_quality(product, constraints, ranked, thresholds)
    matched = matched_constraints(product, constraints)
    sources = []
    if ranked.semantic_rank is not None:
        sources.append("semantic")
    if ranked.keyword_rank is not None:
        sources.append("keyword")
    return HybridSearchResult(
        product_id=product.id,
        title=product.title,
        category=product.category,
        color=product.color,
        material=product.material,
        style=product.style,
        gender=product.gender,
        occasion=product.occasion,
        sizes=product.sizes,
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
        match_quality=quality,
        match_reason=builder.build(product, constraints, ranked, quality),
        ranking=RankingEvidence(
            semantic_similarity=ranked.semantic_similarity,
            semantic_rank=ranked.semantic_rank,
            keyword_score=ranked.keyword_rank_score,
            keyword_rank=ranked.keyword_rank,
            hybrid_score=round(ranked.hybrid_score, 6),
            final_rank=final_rank,
            ranking_sources=sources,
            matched_constraints=matched,
        ),
    )


def hybrid_search(
    request: HybridSearchRequest,
    *,
    settings: Settings | None = None,
    embedder: EmbeddingProvider | None = None,
    constraint_client: Any | None = None,
    resolved_constraints: FashionSearchConstraints | None = None,
    resolved_query: str | None = None,
    sort_preference: str = "RELEVANCE",
) -> HybridSearchResponse:
    """Parse constraints, retrieve, fuse with RRF, and return ranked products."""
    cfg = settings or get_settings()
    try:
        query = normalize_query(request.query)
    except SemanticSearchError as exc:
        raise HybridSearchError(str(exc), status_code=exc.status_code) from exc
    started = time.perf_counter()

    parse_started = time.perf_counter()
    if resolved_constraints is None:
        parsed = parse_constraints(query, settings=cfg, client=constraint_client)
        constraints = parsed.constraints
    else:
        constraints = resolved_constraints
    retrieval_source = resolved_query.strip() if resolved_query else query
    retrieval_query = build_retrieval_query(retrieval_source, constraints)
    parse_ms = (time.perf_counter() - parse_started) * 1000

    if not constraints_currency_supported(constraints, settings=cfg):
        logger.info(
            "hybrid_search unsupported_currency currency=%s", constraints.currency
        )
        return _empty_response(
            query,
            constraints,
            retrieval_query=retrieval_query,
            parse_ms=parse_ms,
            status="unsupported_constraints",
            message=(
                f"Price filters in {constraints.currency} are not supported; "
                f"the catalog uses {cfg.market_currency.upper()}."
            ),
        )

    candidate_limit = max(request.limit, cfg.hybrid_candidate_limit)
    semantic_hits: list[VectorHit] = []
    keyword_hits: list[KeywordHit] = []
    semantic_error: str | None = None
    keyword_error: str | None = None
    embed_ms = 0.0
    semantic_ms = 0.0
    keyword_ms = 0.0

    embed_started = time.perf_counter()
    worker = embedder or get_embedding_provider(cfg)
    provider_name = (
        worker.name
        if isinstance(getattr(worker, "name", None), str)
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
        except Exception:
            logger.exception("embedding_index_status_failed provider=%s", provider_name)
    try:
        if index_status in ("empty", "incompatible"):
            semantic_error = f"embedding index is {index_status}"
            logger.warning(
                "semantic_unavailable provider=%s model=%s dimensions=%s index_status=%s",
                provider_name,
                model_name,
                dimensions,
                index_status,
            )
        else:
            query_vector = worker.embed_query(retrieval_query)
            embed_ms = (time.perf_counter() - embed_started) * 1000
            sem_started = time.perf_counter()
            semantic_hits = search_by_vector(
                query_vector,
                limit=candidate_limit,
                constraints=constraints,
                settings=cfg,
                provider=provider_name,
                model=model_name,
                dimensions=dimensions,
            )
            semantic_ms = (time.perf_counter() - sem_started) * 1000
    except EmbeddingDimensionError as exc:
        semantic_error = str(exc)
    except AIProviderError as exc:
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
    search_mode = {
        "keyword_only": "keyword_fallback",
        "semantic_only": "semantic_fallback",
    }.get(fallback, "hybrid")

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
    if sort_preference in {"PRICE_ASC", "PRICE_DESC"}:
        products_for_price = {
            hit.product.id: hit.product for hit in (*semantic_hits, *keyword_hits)
        }
        reverse = sort_preference == "PRICE_DESC"
        fused.sort(
            key=lambda row: (
                -products_for_price[row.product_id].price_inr
                if reverse
                else products_for_price[row.product_id].price_inr,
                -row.hybrid_score,
                row.product_id,
            )
        )
    fused = fused[: request.limit]
    fusion_ms = (time.perf_counter() - fusion_started) * 1000

    products_by_id: dict[int, Product] = {
        hit.product.id: hit.product for hit in semantic_hits
    }
    for hit in keyword_hits:
        products_by_id.setdefault(hit.product.id, hit.product)

    thresholds = QualityThresholds(
        strong_semantic=getattr(cfg, "search_strong_semantic_threshold", 0.75),
        weak_semantic=getattr(cfg, "search_weak_semantic_threshold", 0.35),
        min_keyword=getattr(cfg, "search_min_keyword_signal", 0.01),
    )
    builder = MatchExplanationBuilder()
    explanation_started = time.perf_counter()
    results = [
        _result_from_product(
            products_by_id[row.product_id],
            row,
            constraints,
            final_rank=index,
            thresholds=thresholds,
            builder=builder,
        )
        for index, row in enumerate(fused, start=1)
        if row.product_id in products_by_id
    ]
    explanation_ms = (time.perf_counter() - explanation_started) * 1000

    diagnostics = None
    suggestions: list[str] = []
    search_status = "success" if results else "no_results"
    message = None if results else "No products were returned for this search."
    diagnostics_ms = 0.0
    if not results and getattr(cfg, "search_diagnostics_enabled", True):
        diagnostics_started = time.perf_counter()
        try:
            diagnostics, suggestions = diagnose_zero_results(constraints)
            if diagnostics.exact_match_count == 0:
                search_status = "no_exact_matches"
                message = "No products matched this exact filter combination in the current catalog."
            else:
                search_status = "no_relevant_matches"
                message = (
                    "Products matched your filters, but none had sufficient "
                    "keyword or semantic relevance to return."
                )
        except Exception:
            logger.exception("hybrid_zero_result_diagnostics_failed")
        diagnostics_ms = (time.perf_counter() - diagnostics_started) * 1000
    total_ms = (time.perf_counter() - started) * 1000

    quality_counts = {
        quality: sum(row.match_quality == quality for row in results)
        for quality in ("strong", "good", "weak")
    }

    logger.info(
        "hybrid_search query_len=%s retrieval_len=%s limit=%s semantic_hits=%s "
        "keyword_hits=%s returned=%s fallback=%s parse_ms=%.1f embed_ms=%.1f "
        "semantic_ms=%.1f keyword_ms=%.1f fusion_ms=%.1f explanation_ms=%.1f "
        "status=%s strong=%s good=%s weak=%s total_ms=%.1f",
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
        explanation_ms,
        search_status,
        quality_counts["strong"],
        quality_counts["good"],
        quality_counts["weak"],
        total_ms,
    )
    return HybridSearchResponse(
        query=query,
        retrieval_query=retrieval_query,
        filters=constraints_to_filters(constraints),
        total=len(results),
        results=results,
        search_status=search_status,
        message=message,
        suggestions=suggestions,
        diagnostics=diagnostics,
        search_mode=search_mode,
        semantic_search_available=semantic_error is None,
        embedding_index_status=index_status,
        metrics={
            "parse_ms": round(parse_ms, 1),
            "embed_ms": round(embed_ms, 1),
            "semantic_ms": round(semantic_ms, 1),
            "keyword_ms": round(keyword_ms, 1),
            "fusion_ms": round(fusion_ms, 1),
            "explanation_ms": round(explanation_ms, 1),
            "diagnostics_ms": round(diagnostics_ms, 1),
            "total_ms": round(total_ms, 1),
            "semantic_candidates": len(semantic_hits),
            "keyword_candidates": len(keyword_hits),
            "fallback": fallback,
            "strong_results": quality_counts["strong"],
            "good_results": quality_counts["good"],
            "weak_results": quality_counts["weak"],
            "zero_results": int(not results),
        },
    )
