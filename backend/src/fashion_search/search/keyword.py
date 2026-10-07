"""PostgreSQL full-text search over catalog text fields.

Day 3 will use `tsvector` / `plainto_tsquery` on title, brand, and description.
"""

from fashion_search.catalog.schemas import ProductFilters, ProductRecord


def search_by_keyword(
    filters: ProductFilters,
    *,
    limit: int = 20,
) -> list[ProductRecord]:
    """Return products matching lexical query terms and structured filters."""
    raise NotImplementedError("Keyword search is scheduled for Day 3.")
