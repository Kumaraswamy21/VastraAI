"""Apply validated fashion constraints as hard SQL filters on product queries."""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import Select

from fashion_search.catalog.models import Product
from fashion_search.config.settings import Settings, get_settings
from fashion_search.search.schemas import FashionSearchConstraints

Stmt = TypeVar("Stmt", bound=Select)


def constraints_currency_supported(
    constraints: FashionSearchConstraints,
    *,
    settings: Settings | None = None,
) -> bool:
    """Return False when monetary filters use an unsupported catalog currency."""
    cfg = settings or get_settings()
    return constraints.currency.upper() == cfg.market_currency.upper()


def apply_search_constraints(stmt: Stmt, constraints: FashionSearchConstraints) -> Stmt:
    """AND exact metadata and price bounds onto a product SELECT."""
    if constraints.category is not None:
        stmt = stmt.where(Product.category == constraints.category)
    if constraints.color is not None:
        stmt = stmt.where(Product.color == constraints.color)
    if constraints.occasion is not None:
        stmt = stmt.where(Product.occasion == constraints.occasion)
    if constraints.gender is not None:
        stmt = stmt.where(Product.gender == constraints.gender)
    if constraints.size is not None:
        stmt = stmt.where(Product.sizes.contains([constraints.size]))
    if constraints.price_min is not None:
        minimum = int(constraints.price_min)
        if constraints.price_min_inclusive:
            stmt = stmt.where(Product.price_inr >= minimum)
        else:
            stmt = stmt.where(Product.price_inr > minimum)
    if constraints.price_max is not None:
        maximum = int(constraints.price_max)
        if constraints.price_max_inclusive:
            stmt = stmt.where(Product.price_inr <= maximum)
        else:
            stmt = stmt.where(Product.price_inr < maximum)
    return stmt
