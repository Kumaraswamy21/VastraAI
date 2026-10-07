"""Merge keyword and vector result lists into a single ranked page.

Day 3 will combine scores (for example Reciprocal Rank Fusion) then apply
price, color, category, and occasion filters.
"""

from fashion_search.catalog.schemas import ProductFilters, ProductRecord


def search_hybrid(
    filters: ProductFilters,
    *,
    limit: int = 20,
) -> list[ProductRecord]:
    """Retrieve and rank catalog items for a parsed shopping query."""
    raise NotImplementedError("Hybrid search is scheduled for Day 3.")
