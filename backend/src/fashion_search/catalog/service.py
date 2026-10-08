"""Catalog browsing business rules. Route handlers stay thin."""

from fashion_search.catalog.queries import ProductListQuery
from fashion_search.catalog.repository import count_products, get_by_slug, list_products
from fashion_search.catalog.schemas import ProductListResponse, ProductRecord


def page_offset(page: int, page_size: int) -> int:
    """Convert a 1-based page number to a SQL OFFSET."""
    return (page - 1) * page_size


def total_pages(total_count: int, page_size: int) -> int:
    """Return page count; empty result sets have zero pages."""
    if total_count == 0 or page_size <= 0:
        return 0
    return (total_count + page_size - 1) // page_size


def to_record(product: object) -> ProductRecord:
    """Map an ORM row to the public product schema."""
    return ProductRecord.model_validate(product, from_attributes=True)


def list_catalog(query: ProductListQuery) -> ProductListResponse:
    """Paginate the filtered catalog without leaking hidden columns."""
    total_count = count_products(query)
    rows = list_products(
        query,
        offset=page_offset(query.page, query.page_size),
        limit=query.page_size,
    )
    return ProductListResponse(
        items=[to_record(row) for row in rows],
        page=query.page,
        page_size=query.page_size,
        total_count=total_count,
        total_pages=total_pages(total_count, query.page_size),
    )


def get_catalog_product(slug: str) -> ProductRecord | None:
    """Return a public product, or None when the slug is unknown."""
    row = get_by_slug(slug)
    if row is None:
        return None
    return to_record(row)
