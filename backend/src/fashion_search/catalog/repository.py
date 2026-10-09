"""SQL access for catalog browsing. Never selects embedding or search_vector."""

from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, load_only

from fashion_search.catalog.models import Product
from fashion_search.catalog.queries import ProductListQuery, SortOption
from fashion_search.core.db import get_engine

Stmt = TypeVar("Stmt", bound=Select)

HIDDEN_COLUMNS = frozenset(
    {
        "embedding",
        "search_vector",
        "embedding_provider",
        "embedding_model",
        "embedding_dimensions",
        "embedding_text_hash",
        "embedding_status",
        "embedding_generated_at",
        "embedding_error",
    }
)


def public_column_attrs() -> list[object]:
    """Instrumented columns that are safe to return from the API."""
    return [
        getattr(Product, column.key)
        for column in Product.__table__.columns
        if column.key not in HIDDEN_COLUMNS
    ]


def public_load_options():
    """Restrict ORM loads to public columns only."""
    return load_only(*public_column_attrs())


def base_product_select() -> Select[tuple[Product]]:
    """Start a product query that cannot load hidden columns."""
    return select(Product).options(public_load_options())


def apply_filters(stmt: Stmt, query: ProductListQuery) -> Stmt:
    """AND exact equality, size containment, and inclusive price bounds."""
    if query.category is not None:
        stmt = stmt.where(Product.category == query.category)
    if query.color is not None:
        stmt = stmt.where(Product.color == query.color)
    if query.gender is not None:
        stmt = stmt.where(Product.gender == query.gender)
    if query.occasion is not None:
        stmt = stmt.where(Product.occasion == query.occasion)
    if query.style is not None:
        stmt = stmt.where(Product.style == query.style)
    if query.size is not None:
        stmt = stmt.where(Product.sizes.contains([query.size]))
    if query.min_price is not None:
        stmt = stmt.where(Product.price_inr >= query.min_price)
    if query.max_price is not None:
        stmt = stmt.where(Product.price_inr <= query.max_price)
    return stmt


def apply_sort(
    stmt: Select[tuple[Product]], sort: SortOption
) -> Select[tuple[Product]]:
    """Sort by insert order (id) or unit price."""
    if sort == "price_asc":
        return stmt.order_by(Product.price_inr.asc(), Product.id.asc())
    if sort == "price_desc":
        return stmt.order_by(Product.price_inr.desc(), Product.id.desc())
    return stmt.order_by(Product.id.desc())


def count_products(query: ProductListQuery) -> int:
    """Return the filtered catalog size."""
    stmt = apply_filters(select(func.count()).select_from(Product), query)
    with get_engine().connect() as connection:
        return int(connection.scalar(stmt) or 0)


def list_products(query: ProductListQuery, offset: int, limit: int) -> list[Product]:
    """Return one page of public product rows."""
    stmt = apply_sort(apply_filters(base_product_select(), query), query.sort)
    stmt = stmt.offset(offset).limit(limit)
    with Session(get_engine(), expire_on_commit=False) as session:
        return list(session.scalars(stmt).all())


def get_by_slug(slug: str) -> Product | None:
    """Return one public product row, or None if the slug is unknown."""
    stmt = base_product_select().where(Product.slug == slug)
    with Session(get_engine(), expire_on_commit=False) as session:
        return session.scalars(stmt).first()
