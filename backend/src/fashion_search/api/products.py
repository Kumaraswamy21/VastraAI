"""HTTP routes for catalog browsing. Handlers delegate to the catalog service."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from fashion_search.catalog.queries import ProductListQuery
from fashion_search.catalog.schemas import ProductListResponse, ProductRecord
from fashion_search.catalog.service import get_catalog_product, list_catalog

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
def list_products(
    params: Annotated[ProductListQuery, Query()],
) -> ProductListResponse:
    """Return a filtered, paginated catalog page."""
    return list_catalog(params)


@router.get("/{slug}", response_model=ProductRecord)
def get_product(slug: str) -> ProductRecord:
    """Return one catalog product by slug."""
    product = get_catalog_product(slug)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {slug}")
    return product
