"""pgvector cosine-similarity retrieval over Gemini product embeddings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fashion_search.catalog.models import Product
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine


@dataclass(frozen=True)
class VectorHit:
    """One product row with cosine similarity to the query embedding."""

    product: Product
    similarity_score: float


def search_by_vector(
    query_embedding: list[float],
    *,
    limit: int = 10,
    settings: Settings | None = None,
) -> list[VectorHit]:
    """Return products ordered by cosine distance to the query vector.

    Only COMPLETED Gemini embeddings matching the configured model and
    dimensions are considered. Exact search is used (no HNSW) for the
    current catalog size.
    """
    cfg = settings or get_settings()
    if limit < 1:
        return []
    if len(query_embedding) != cfg.embedding_dimensions:
        raise ValueError(
            f"query embedding has {len(query_embedding)} dims; "
            f"expected {cfg.embedding_dimensions}"
        )

    distance = Product.embedding.cosine_distance(query_embedding)
    similarity = (1 - distance).label("similarity_score")
    statement = (
        select(Product, similarity)
        .where(Product.embedding.is_not(None))
        .where(Product.embedding_status == "COMPLETED")
        .where(Product.embedding_provider == "gemini")
        .where(Product.embedding_model == cfg.embedding_model)
        .where(Product.embedding_dimensions == cfg.embedding_dimensions)
        .order_by(distance)
        .limit(limit)
    )
    with Session(get_engine(), expire_on_commit=False) as session:
        rows = session.execute(statement).all()
        return [
            VectorHit(product=row[0], similarity_score=float(row[1]))
            for row in rows
        ]
