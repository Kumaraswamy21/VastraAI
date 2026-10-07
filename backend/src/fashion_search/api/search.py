"""Catalog search HTTP API. Retrieval is not implemented on Day 1."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fashion_search.catalog.schemas import ProductFilters, ProductRecord

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
    """Run hybrid catalog search. Day 3 implements retrieval."""
    raise HTTPException(
        status_code=501,
        detail="Search is not implemented on Day 1.",
    )
