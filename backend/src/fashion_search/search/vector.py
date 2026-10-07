"""pgvector nearest-neighbor retrieval.

Day 3 will embed the query and search `products.embedding`.
"""

from fashion_search.catalog.schemas import ProductFilters, ProductRecord


def search_by_vector(
    filters: ProductFilters,
    *,
    limit: int = 20,
) -> list[ProductRecord]:
    """Return products nearest to the query embedding.

    Intended path: embed `filters.query_text`, filter by structured fields,
    then ORDER BY embedding <=> query_vector.
    """
    raise NotImplementedError("Vector search is scheduled for Day 3.")
