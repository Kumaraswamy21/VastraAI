"""pgvector retrieval constrained to one explicit embedding space."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from fashion_search.catalog.models import Product
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine
from fashion_search.search.filters import apply_search_constraints
from fashion_search.search.schemas import FashionSearchConstraints


@dataclass(frozen=True)
class VectorHit:
    """One product row with cosine similarity to the query embedding."""

    product: Product
    similarity_score: float


def embedding_index_status(*, provider: str, model: str, dimensions: int) -> str:
    """Return compatibility of stored vectors with one configured vector space."""
    completed = Product.embedding_status == "COMPLETED"
    compatible_space = (
        (Product.embedding_provider == provider)
        & (Product.embedding_model == model)
        & (Product.embedding_dimensions == dimensions)
    )
    incompatible_space = or_(
        Product.embedding_provider.is_distinct_from(provider),
        Product.embedding_model.is_distinct_from(model),
        Product.embedding_dimensions.is_distinct_from(dimensions),
    )
    statement = select(
        func.count(Product.id).filter(Product.embedding.is_not(None)).label("total"),
        func.count(Product.id)
        .filter(
            completed,
            Product.embedding.is_not(None),
            compatible_space,
        )
        .label("compatible"),
        func.count(Product.id)
        .filter(Product.embedding.is_not(None), incompatible_space)
        .label("incompatible"),
    )
    with Session(get_engine()) as session:
        row = session.execute(statement).one()
    if int(row.incompatible) > 0:
        return "incompatible"
    if int(row.compatible) > 0:
        return "ready"
    return "empty"


def search_by_vector(
    query_embedding: list[float],
    *,
    limit: int = 10,
    constraints: FashionSearchConstraints | None = None,
    settings: Settings | None = None,
    provider: str | None = None,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[VectorHit]:
    """Return products ordered by cosine distance to the query vector.

    Only COMPLETED embeddings matching the configured provider, model, and
    dimensions are considered. Exact search is used (no HNSW) for the
    current catalog size.
    """
    cfg = settings or get_settings()
    if limit < 1:
        return []
    active_provider = provider or cfg.embedding_provider
    active_model = model or cfg.embedding_model
    active_dimensions = dimensions or cfg.embedding_dimensions
    if len(query_embedding) != active_dimensions:
        raise ValueError(
            f"query embedding has {len(query_embedding)} dims; "
            f"expected {active_dimensions}"
        )

    distance = Product.embedding.cosine_distance(query_embedding)
    similarity = (1 - distance).label("similarity_score")
    statement = (
        select(Product, similarity)
        .where(Product.embedding.is_not(None))
        .where(Product.embedding_status == "COMPLETED")
        .where(Product.embedding_provider == active_provider)
        .where(Product.embedding_model == active_model)
        .where(Product.embedding_dimensions == active_dimensions)
    )
    if constraints is not None:
        statement = apply_search_constraints(statement, constraints)
    statement = statement.order_by(distance).limit(limit)
    with Session(get_engine(), expire_on_commit=False) as session:
        rows = session.execute(statement).all()
        return [
            VectorHit(product=row[0], similarity_score=float(row[1])) for row in rows
        ]
