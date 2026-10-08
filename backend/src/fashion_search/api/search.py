"""Catalog search HTTP API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fashion_search.catalog.schemas import ProductFilters, ProductRecord
from fashion_search.search.schemas import SemanticSearchRequest, SemanticSearchResponse
from fashion_search.search.semantic import SemanticSearchError, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    """Natural-language search, optionally with already-parsed filters."""

    query: str = Field(min_length=1)
    filters: ProductFilters | None = None
    limit: int = Field(default=20, ge=1, le=50)


class SearchResponse(BaseModel):
    """Ranked product cards for the shopper."""

    products: list[ProductRecord]
    message: str = ""


@router.post("", response_model=SearchResponse)
def search_catalog(_body: SearchRequest) -> SearchResponse:
    """Hybrid catalog search (keyword + vector). Not implemented yet."""
    raise HTTPException(
        status_code=501,
        detail="Hybrid search is not implemented yet. Use POST /search/semantic.",
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
def search_semantic(body: SemanticSearchRequest) -> SemanticSearchResponse:
    """Rank products by Gemini query embedding + pgvector cosine similarity."""
    try:
        return semantic_search(body)
    except SemanticSearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
