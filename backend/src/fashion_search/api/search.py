"""Catalog search HTTP API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fashion_search.search.schemas import (
    ConstraintParseRequest,
    ConstraintParseResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from fashion_search.search.constraints import parse_constraints
from fashion_search.search.hybrid import HybridSearchError, hybrid_search
from fashion_search.search.semantic import SemanticSearchError, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    """Natural-language hybrid search (alias of HybridSearchRequest)."""

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=50)


@router.post("", response_model=HybridSearchResponse)
def search_catalog(body: SearchRequest) -> HybridSearchResponse:
    """Hybrid catalog search: constraints, semantic + keyword, RRF fusion."""
    try:
        return hybrid_search(
            HybridSearchRequest(query=body.query, limit=body.limit),
        )
    except HybridSearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/hybrid", response_model=HybridSearchResponse)
def search_hybrid(body: HybridSearchRequest) -> HybridSearchResponse:
    """Explicit hybrid search endpoint (same behavior as POST /search)."""
    try:
        return hybrid_search(body)
    except HybridSearchError as exc:
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
