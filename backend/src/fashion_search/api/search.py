"""Catalog and conversational search HTTP API."""

import hashlib
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
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
)
from fashion_search.search.constraints import parse_constraints
from fashion_search.search.hybrid import HybridSearchError, hybrid_search
from fashion_search.search.sessions import search_session_store
from fashion_search.search.semantic import SemanticSearchError, semantic_search

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
        semantic_candidate_count=metrics.get("semantic_candidates"),
        keyword_candidate_count=metrics.get("keyword_candidates"),
        final_result_count=result.total if result else None,
        generation_provider=getattr(cfg, "generation_provider", None),
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


@router.post("", response_model=ConversationalSearchResponse)
def search_catalog(body: SearchRequest) -> ConversationalSearchResponse:
    """Create or refine structured state, then execute the existing hybrid search."""
    started = time.perf_counter()
    identifier = request_id()
    search_request_id_var.set(identifier)
    session_id = body.session_id
    message = body.query or body.message or ""
    try:
        if not body.session_id:
            message = body.query or body.message or ""
            state = initial_search_state(message)
            session_id, state = search_session_store.create(state)
            interpreted_as: Literal["initial", "refinement", "new_search"] = "initial"
        else:
            session_id = body.session_id
            current = search_session_store.get(session_id)
            if current is None:
                raise HTTPException(status_code=404, detail="search session not found")
            message = body.message or "Updated filters"
            refinement = (
                SearchRefinement(updates=body.updates or [])
                if body.updates is not None
                else FollowUpInterpreter(GenerationRouter()).interpret(message, current)
            )
            state = SearchStateReducer().apply(
                current,
                refinement,
                message=message,
                expected_revision=body.expected_revision
                if body.expected_revision is not None
                else -1,
            )
            search_session_store.commit(
                session_id, state, expected_revision=current.revision
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
def search_hybrid(body: HybridSearchRequest) -> HybridSearchResponse:
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


@router.post("/semantic", response_model=SemanticSearchResponse)
def search_semantic(body: SemanticSearchRequest) -> SemanticSearchResponse:
    """Rank products by configured query embedding + pgvector cosine similarity."""
    try:
        return semantic_search(body)
    except SemanticSearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/parse", response_model=ConstraintParseResponse)
def parse_search_constraints(body: ConstraintParseRequest) -> ConstraintParseResponse:
    """Extract query constraints without applying them to retrieval."""
    return parse_constraints(body.query)
