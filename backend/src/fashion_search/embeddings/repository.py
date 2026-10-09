"""Persist provider-identified product embeddings and generation state."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from fashion_search.catalog.models import Product
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine


def product_as_mapping(product: Product) -> dict[str, Any]:
    """Public catalog fields used for embedding text (no IDs or price)."""
    return {
        "title": product.title,
        "category": product.category,
        "color": product.color,
        "material": product.material,
        "style": product.style,
        "occasion": product.occasion,
        "gender": product.gender,
        "description": product.description,
    }


def needs_embedding(
    product: Product,
    *,
    text_digest: str,
    model: str,
    dimensions: int,
    provider: str = "gemini",
) -> bool:
    """True when the product should be (re)embedded for the active config."""
    if product.embedding_status == "FAILED":
        return True
    if product.embedding_status != "COMPLETED":
        return True
    if product.embedding is None:
        return True
    if product.embedding_text_hash != text_digest:
        return True
    if product.embedding_model != model:
        return True
    if product.embedding_dimensions != dimensions:
        return True
    if product.embedding_provider != provider:
        return True
    return False


def recover_stale_processing(settings: Settings | None = None) -> int:
    """Reset interrupted PROCESSING rows so the pipeline can retry them."""
    cfg = settings or get_settings()
    cutoff = datetime.now(UTC) - timedelta(minutes=cfg.embedding_stale_processing_minutes)
    statement = (
        update(Product)
        .where(Product.embedding_status == "PROCESSING")
        .where(
            or_(
                Product.embedding_generated_at.is_(None),
                Product.embedding_generated_at < cutoff,
            )
        )
        .values(
            embedding_status="FAILED",
            embedding_error="stale PROCESSING recovered after interruption",
        )
    )
    with get_engine().begin() as connection:
        result = connection.execute(statement)
        return int(result.rowcount or 0)


def iter_product_batches(batch_size: int, *, limit: int | None = None):
    """Yield ORM product batches ordered by id without loading the full catalog."""
    last_id = 0
    yielded = 0
    while True:
        remaining = None if limit is None else max(0, limit - yielded)
        if remaining == 0:
            break
        take = batch_size if remaining is None else min(batch_size, remaining)
        with Session(get_engine(), expire_on_commit=False) as session:
            rows = list(
                session.scalars(
                    select(Product)
                    .where(Product.id > last_id)
                    .order_by(Product.id.asc())
                    .limit(take)
                ).all()
            )
        if not rows:
            break
        yielded += len(rows)
        last_id = rows[-1].id
        yield rows


def mark_processing(product_ids: list[int]) -> None:
    """Claim products before calling the configured embedding provider."""
    if not product_ids:
        return
    statement = (
        update(Product)
        .where(Product.id.in_(product_ids))
        .values(
            embedding_status="PROCESSING",
            embedding_error=None,
            embedding_generated_at=datetime.now(UTC),
        )
    )
    with get_engine().begin() as connection:
        connection.execute(statement)


def save_completed(
    *,
    product_id: int,
    vector: list[float],
    text_digest: str,
    provider: str,
    model: str,
    dimensions: int,
) -> None:
    """Persist a validated vector and COMPLETED metadata atomically."""
    statement = (
        update(Product)
        .where(Product.id == product_id)
        .values(
            embedding=vector,
            embedding_provider=provider,
            embedding_model=model,
            embedding_dimensions=dimensions,
            embedding_text_hash=text_digest,
            embedding_status="COMPLETED",
            embedding_generated_at=datetime.now(UTC),
            embedding_error=None,
        )
    )
    with get_engine().begin() as connection:
        connection.execute(statement)


def save_failed(product_id: int, error: str) -> None:
    """Record a FAILED generation attempt without clearing prior vectors."""
    statement = (
        update(Product)
        .where(Product.id == product_id)
        .values(
            embedding_status="FAILED",
            embedding_error=error[:2000],
            embedding_generated_at=datetime.now(UTC),
        )
    )
    with get_engine().begin() as connection:
        connection.execute(statement)
