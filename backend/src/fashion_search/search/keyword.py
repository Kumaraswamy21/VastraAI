"""PostgreSQL full-text search over weighted product search_vector."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fashion_search.catalog.models import Product
from fashion_search.core.db import get_engine
from fashion_search.search.filters import apply_search_constraints
from fashion_search.search.schemas import FashionSearchConstraints


@dataclass(frozen=True)
class KeywordHit:
    """One product row with FTS relevance."""

    product: Product
    rank_score: float


def search_by_keyword(
    query: str,
    *,
    constraints: FashionSearchConstraints,
    limit: int = 50,
) -> list[KeywordHit]:
    """Rank products with websearch_to_tsquery and ts_rank_cd."""
    cleaned = (query or "").strip()
    if limit < 1 or not cleaned:
        return []

    tsquery = func.websearch_to_tsquery("english", cleaned)
    rank = func.ts_rank_cd(Product.search_vector, tsquery).label("rank_score")
    statement = (
        select(Product, rank)
        .where(Product.search_vector.is_not(None))
        .where(Product.search_vector.op("@@")(tsquery))
    )
    statement = apply_search_constraints(statement, constraints)
    statement = statement.order_by(rank.desc(), Product.id.asc()).limit(limit)

    with Session(get_engine(), expire_on_commit=False) as session:
        rows = session.execute(statement).all()
        return [KeywordHit(product=row[0], rank_score=float(row[1])) for row in rows]
