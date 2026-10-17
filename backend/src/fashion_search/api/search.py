"""Catalog and conversational search HTTP API."""

import hashlib
import time
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fashion_search.generation.router import GenerationRouter
from fashion_search.config.settings import get_settings
from fashion_search.core.logging import get_logger
from fashion_search.observability.context import request_id, search_request_id_var
from fashion_search.observability.repository import repository as telemetry_repository
from fashion_search.observability.schemas import SearchEventData
from fashion_search.search.conversation import (
    FollowUpInterpreter,
    RevisionConflictError,
    SearchStateReducer,
    StateTransitionError,
    active_filters,
    deterministic_refinement,
    initial_search_state,
)

from fashion_search.search.schemas import (
    ConstraintParseRequest,
    ConstraintParseResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    ActiveFilter,
    ConstraintUpdate,
    SearchRefinement,
    SearchState,
    SemanticSearchRequest,
    SemanticSearchResponse,
    FashionSearchConstraints,
)
from fashion_search.search.constraints import (
    parse_constraints,
)
from fashion_search.search.hybrid import HybridSearchError, hybrid_search
from fashion_search.search.preprocess import build_retrieval_query
from fashion_search.search.sessions import search_session_store
from fashion_search.auth.security import current_user
from fashion_search.catalog.models import User
from fashion_search.search.semantic import SemanticSearchError, semantic_search
from fashion_search.rag.service import generate_grounded_answer, needs_grounded_answer
from fashion_search.rag.shopify import generate_shopify_grounded_answer
from fashion_search.shopify.mcp_client import (
    ShopifyMcpClient,
    ShopifyMcpError,
    ShopifyMcpProtocolError,
    ShopifyMcpRateLimitError,
    ShopifyMcpTimeoutError,
)
from fashion_search.shopify.schemas import (
    ShopifyConversationalSearchResponse,
    ShopifyProductResult,
    map_shopify_products,
)

router = APIRouter(prefix="/search", tags=["search"])
logger = get_logger(__name__)


def _record_search(
    result: HybridSearchResponse | None,
    *,
    started: float,
    session_id: str | None,
    query: str,
    error_type: str | None = None,
) -> str:
    identifier = search_request_id_var.get() or request_id()
    cfg = get_settings()
    metrics = result.metrics if result else {}
    mode = result.search_mode.upper() if result else "FAILED"
    fallback = bool(metrics.get("fallback")) if result else False
    event = SearchEventData(
        request_id=identifier,
        session_id=session_id,
        search_mode=mode,
        outcome=(
            "SUCCESS"
            if result and result.search_status == "success"
            else "ZERO_RESULTS"
            if result and result.total == 0
            else "FAILED"
        ),
        total_latency_ms=(time.perf_counter() - started) * 1000,
        constraint_parsing_ms=metrics.get("parse_ms"),
        query_embedding_ms=metrics.get("embed_ms"),
        semantic_search_ms=metrics.get("semantic_ms"),
        keyword_search_ms=metrics.get("keyword_ms"),
        fusion_ms=metrics.get("fusion_ms"),
        explanation_ms=metrics.get("explanation_ms"),
        retrieval_latency_ms=metrics.get("retrieval_latency_ms"),
        rag_generation_latency_ms=metrics.get("rag_generation_latency_ms"),
        total_rag_latency_ms=metrics.get("total_rag_latency_ms"),
        retrieved_context_count=metrics.get("retrieved_context_count"),
        context_size_chars=metrics.get("context_size_chars"),
        generation_provider=metrics.get("generation_provider"),
        generation_model=metrics.get("generation_model"),
        grounding_failure=bool(metrics.get("grounding_failure", False)),
        invalid_product_reference=bool(metrics.get("invalid_product_reference", False)),
        semantic_candidate_count=metrics.get("semantic_candidates"),
        keyword_candidate_count=metrics.get("keyword_candidates"),
        final_result_count=result.total if result else None,
        embedding_provider=getattr(cfg, "embedding_provider", None),
        fallback_used=fallback,
        semantic_search_available=result.semantic_search_available if result else False,
        error_type=error_type,
        query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest() if query else None,
        redacted_query=query if cfg.observability_store_raw_queries else None,
    )
    try:
        telemetry_repository.record_search(event)
    except Exception as exc:
        logger.warning(
            "telemetry_search_write_failed error_type=%s", type(exc).__name__
        )
    return identifier


class SearchRequest(BaseModel):
    """Initial query, natural-language follow-up, or structured filter update."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str | None = Field(default=None, min_length=1, max_length=500)
    message: str | None = Field(default=None, min_length=1, max_length=500)
    session_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    updates: list[ConstraintUpdate] | None = None
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_turn(self) -> "SearchRequest":
        if self.session_id:
            if self.expected_revision is None:
                raise ValueError("expected_revision is required for a follow-up")
            if not self.message and not self.updates:
                raise ValueError("message or updates is required for a follow-up")
        elif not (self.query or self.message):
            raise ValueError("query or message is required for an initial search")
        return self


class ConversationalSearchResponse(HybridSearchResponse):
    session_id: str
    revision: int
    interpreted_as: Literal["initial", "refinement", "new_search"]
    state: SearchState
    active_filters: list[ActiveFilter]


@router.post(
    "",
    response_model=ConversationalSearchResponse | ShopifyConversationalSearchResponse,
)
def search_catalog(
    body: SearchRequest,
    provider: Literal["local", "shopify"] = Query(default="local"),
    user: User = Depends(current_user),
) -> ConversationalSearchResponse | ShopifyConversationalSearchResponse:
    """Create or refine structured state, then execute the existing hybrid search."""
    if provider == "shopify":
        started = time.perf_counter()
        identifier = request_id()
        search_request_id_var.set(identifier)
        session_id = body.session_id
        message = body.query or body.message or ""
        try:
            if not body.session_id:
                state = initial_search_state(message)
                session_id, state = search_session_store.create(user.id, state)
                interpreted_as: Literal["initial", "refinement", "new_search"] = (
                    "initial"
                )
            else:
                current = search_session_store.get(user.id, body.session_id)
                if current is None:
                    raise HTTPException(
                        status_code=404, detail="search session not found"
                    )
                message = body.message or "Updated filters"
                if body.updates is not None:
                    refinement = SearchRefinement(updates=body.updates)
                else:
                    refinement = deterministic_refinement(message, current)
                    if refinement is None and needs_grounded_answer(message):
                        refinement = SearchRefinement()
                    elif refinement is None:
                        refinement = FollowUpInterpreter(GenerationRouter()).interpret(
                            message, current
                        )
                state = SearchStateReducer().apply(
                    current,
                    refinement,
                    message=message,
                    expected_revision=body.expected_revision
                    if body.expected_revision is not None
                    else -1,
                )
                interpreted_as = (
                    "new_search" if refinement.reset_search else "refinement"
                )

            assert session_id is not None
            settings = get_settings()
            if not settings.shopify_catalog_enabled:
                raise HTTPException(
                    status_code=503, detail="Shopify catalog search is not enabled"
                )
            currency = state.constraints.currency.upper()
            query = _shopify_retrieval_query(state)
            filters: dict[str, object] = {
                "available": True,
                "ships_to": {"country": settings.shopify_catalog_country.upper()},
            }
            if currency == settings.market_currency.upper():
                price_filter = _shopify_price_filter(state.constraints, currency)
                if price_filter:
                    filters["price"] = price_filter
            with ShopifyMcpClient(settings) as shopify_client:
                content = shopify_client.search_catalog(
                    query,
                    limit=body.limit,
                    currency=currency,
                    filters=filters,
                )
            products = [
                product
                for product in map_shopify_products(content.get("products"))
                if product.available is not False
                and _shopify_product_matches_price(product, state.constraints)
            ]
            if state.sort_preference in {"PRICE_ASC", "PRICE_DESC"}:
                reverse = state.sort_preference == "PRICE_DESC"
                products.sort(
                    key=lambda product: (
                        product.price_min is None,
                        product.price_min or Decimal("0"),
                    ),
                    reverse=reverse,
                )

            answer = None
            referenced_product_ids: list[str] = []
            rag_metrics: dict[str, object] = {}
            if (
                getattr(settings, "rag_enabled", True)
                and products
                and needs_grounded_answer(message)
            ):
                rag_result = generate_shopify_grounded_answer(
                    message, products, settings=settings
                )
                answer = rag_result.answer
                referenced_product_ids = rag_result.referenced_product_ids
                rag_metrics = {
                    "rag_generation_latency_ms": round(
                        rag_result.generation_latency_ms, 1
                    ),
                    "total_rag_latency_ms": round(
                        (time.perf_counter() - started) * 1000, 1
                    ),
                    "retrieved_context_count": rag_result.context_count,
                    "context_size_chars": rag_result.context_size_chars,
                    "generation_provider": rag_result.generation_provider,
                    "generation_model": rag_result.generation_model,
                    "grounding_failure": rag_result.grounding_failure,
                    "invalid_product_reference": rag_result.invalid_product_reference,
                }
            if body.session_id:
                try:
                    search_session_store.commit(
                        user.id,
                        session_id,
                        state,
                        expected_revision=state.revision - 1,
                    )
                except KeyError as exc:
                    raise HTTPException(
                        status_code=404, detail="search session not found"
                    ) from exc
            pagination = content.get("pagination")
            return ShopifyConversationalSearchResponse(
                query=state.original_query,
                total=len(products),
                results=products,
                has_next_page=(
                    bool(pagination.get("has_next_page", False))
                    if isinstance(pagination, dict)
                    else False
                ),
                session_id=session_id,
                revision=state.revision,
                interpreted_as=interpreted_as,
                state=state,
                active_filters=active_filters(state),
                answer=answer,
                referenced_product_ids=referenced_product_ids,
                metrics=rag_metrics,
            )
        except RevisionConflictError as exc:
            _record_search(
                None,
                started=started,
                session_id=session_id,
                query=message,
                error_type="REVISION_CONFLICT",
            )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except StateTransitionError as exc:
            _record_search(
                None,
                started=started,
                session_id=session_id,
                query=message,
                error_type="INVALID_SEARCH_STATE",
            )
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ShopifyMcpRateLimitError as exc:
            headers = {"Retry-After": exc.retry_after} if exc.retry_after else None
            raise HTTPException(
                status_code=429, detail=str(exc), headers=headers
            ) from exc
        except ShopifyMcpTimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except ShopifyMcpProtocolError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ShopifyMcpError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    started = time.perf_counter()
    identifier = request_id()
    search_request_id_var.set(identifier)
    session_id = body.session_id
    message = body.query or body.message or ""
    try:
        if not body.session_id:
            message = body.query or body.message or ""
            state = initial_search_state(message)
            session_id, state = search_session_store.create(user.id, state)
            interpreted_as: Literal["initial", "refinement", "new_search"] = "initial"
        else:
            session_id = body.session_id
            current = search_session_store.get(user.id, session_id)
            if current is None:
                raise HTTPException(status_code=404, detail="search session not found")
            message = body.message or "Updated filters"
            if body.updates is not None:
                refinement = SearchRefinement(updates=body.updates)
            else:
                refinement = deterministic_refinement(message, current)
                if refinement is None and needs_grounded_answer(message):
                    # Product-context questions leave constraints untouched and
                    # go to grounded generation after the same retrieval reruns.
                    refinement = SearchRefinement()
                elif refinement is None:
                    refinement = FollowUpInterpreter(GenerationRouter()).interpret(
                        message, current
                    )
            state = SearchStateReducer().apply(
                current,
                refinement,
                message=message,
                expected_revision=body.expected_revision
                if body.expected_revision is not None
                else -1,
            )
            interpreted_as = "new_search" if refinement.reset_search else "refinement"

        semantic_query = " ".join(
            [state.semantic_query, *state.semantic_modifiers]
        ).strip()
        result = hybrid_search(
            HybridSearchRequest(query=state.current_query, limit=body.limit),
            resolved_constraints=state.constraints,
            resolved_query=semantic_query,
            sort_preference=state.sort_preference,
        )
        cfg = get_settings()
        if (
            getattr(cfg, "rag_enabled", True)
            and result.search_status == "success"
            and result.results
            and needs_grounded_answer(message)
        ):
            rag_result = generate_grounded_answer(
                message, state.constraints, result.results, settings=cfg
            )
            result.answer = rag_result.answer
            result.referenced_product_ids = rag_result.referenced_product_ids
            result.metrics.update(
                {
                    "rag_generation_latency_ms": round(
                        rag_result.generation_latency_ms, 1
                    ),
                    "total_rag_latency_ms": round(
                        float(result.metrics.get("retrieval_latency_ms", 0.0))
                        + rag_result.total_latency_ms,
                        1,
                    ),
                    "retrieved_context_count": rag_result.context_count,
                    "context_size_chars": rag_result.context_size_chars,
                    "generation_provider": rag_result.generation_provider,
                    "generation_model": rag_result.generation_model,
                    "grounding_failure": rag_result.grounding_failure,
                    "invalid_product_reference": rag_result.invalid_product_reference,
                }
            )
        if body.session_id and session_id:
            # Only commit after retrieval has completed so a failed refinement
            # cannot advance the authoritative revision without new results.
            try:
                search_session_store.commit(
                    user.id, session_id, state, expected_revision=state.revision - 1
                )
            except KeyError as exc:
                raise HTTPException(
                    status_code=404, detail="search session not found"
                ) from exc
        result_payload = (
            result.model_dump() if hasattr(result, "model_dump") else vars(result)
        )
        result_payload.pop("request_id", None)
        identifier = _record_search(
            result, started=started, session_id=session_id, query=message
        )
        return ConversationalSearchResponse(
            **result_payload,
            session_id=session_id,
            revision=state.revision,
            interpreted_as=interpreted_as,
            state=state,
            active_filters=active_filters(state),
            request_id=identifier,
        )
    except RevisionConflictError as exc:
        _record_search(
            None,
            started=started,
            session_id=session_id,
            query=message,
            error_type="REVISION_CONFLICT",
        )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StateTransitionError as exc:
        _record_search(
            None,
            started=started,
            session_id=session_id,
            query=message,
            error_type="INVALID_SEARCH_STATE",
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HybridSearchError as exc:
        _record_search(
            None,
            started=started,
            session_id=session_id,
            query=message,
            error_type="SEARCH_ERROR",
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/hybrid", response_model=HybridSearchResponse)
def search_hybrid(
    body: HybridSearchRequest, _user: User = Depends(current_user)
) -> HybridSearchResponse:
    """Explicit hybrid search endpoint (same behavior as POST /search)."""
    started = time.perf_counter()
    identifier = request_id()
    search_request_id_var.set(identifier)
    try:
        result = hybrid_search(body)
        result.request_id = _record_search(
            result, started=started, session_id=None, query=body.query
        )
        return result
    except HybridSearchError as exc:
        _record_search(
            None,
            started=started,
            session_id=None,
            query=body.query,
            error_type="SEARCH_ERROR",
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _shopify_product_matches_price(
    product: ShopifyProductResult, constraints: FashionSearchConstraints
) -> bool:
    """Enforce current session bounds against each returned live price range."""
    if constraints.price_min is None and constraints.price_max is None:
        return True
    currency = constraints.currency.upper()
    if product.currency != currency:
        return False
    if constraints.price_max is not None:
        if product.price_min is None or product.price_min > constraints.price_max:
            return False
        if (
            product.price_min == constraints.price_max
            and constraints.price_max_inclusive is False
        ):
            return False
    if constraints.price_min is not None:
        if product.price_max is None or product.price_max < constraints.price_min:
            return False
        if (
            product.price_max == constraints.price_min
            and constraints.price_min_inclusive is False
        ):
            return False
    return True


def _shopify_price_filter(
    constraints: FashionSearchConstraints, currency: str
) -> dict[str, int]:
    """Convert price bounds to Shopify minor currency units."""
    zero_decimal = {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "ISK",
        "JPY",
        "KMF",
        "KRW",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
    three_decimal = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}
    exponent = 0 if currency in zero_decimal else 3 if currency in three_decimal else 2
    scale = Decimal(10) ** exponent
    result: dict[str, int] = {}
    if constraints.price_min is not None:
        scaled = constraints.price_min * scale
        rounding = ROUND_CEILING if constraints.price_min_inclusive else ROUND_FLOOR
        value = int(scaled.to_integral_value(rounding=rounding))
        if constraints.price_min_inclusive is False and Decimal(value) == scaled:
            value += 1
        result["min"] = value
    if constraints.price_max is not None:
        scaled = constraints.price_max * scale
        result["max"] = int(scaled.to_integral_value(rounding=ROUND_FLOOR))
    return result


def _shopify_retrieval_query(state: SearchState) -> str:
    """Use current search intent and current filters, dropping stale values."""
    semantic = " ".join([state.semantic_query, *state.semantic_modifiers]).strip()
    query = build_retrieval_query(semantic, state.constraints)
    # Shopify's catalog search performs best with normalized category before
    # color. build_retrieval_query appends color before category for local FTS.
    for facet in (state.constraints.category, state.constraints.color):
        if facet and query.casefold().endswith(facet.casefold()):
            query = query[: -len(facet)].rstrip()
    extra = [
        state.constraints.occasion,
        state.constraints.size,
        state.constraints.gender,
    ]
    indexed_facets = [state.constraints.category, state.constraints.color]
    return " ".join(
        [
            query,
            *(value for value in indexed_facets if value),
            *(value for value in extra if value),
        ]
    ).strip()


@router.post("/semantic", response_model=SemanticSearchResponse)
def search_semantic(
    body: SemanticSearchRequest, _user: User = Depends(current_user)
) -> SemanticSearchResponse:
    """Rank products by configured query embedding + pgvector cosine similarity."""
    try:
        return semantic_search(body)
    except SemanticSearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/parse", response_model=ConstraintParseResponse)
def parse_search_constraints(
    body: ConstraintParseRequest, _user: User = Depends(current_user)
) -> ConstraintParseResponse:
    """Extract query constraints without applying them to retrieval."""
    return parse_constraints(body.query)
