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
    if constraints.price_min is None and constraints.price_max is None:
        return True
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
        if constraints.price_min_inclusive:
            stmt = stmt.where(Product.price_inr >= constraints.price_min)
        else:
            stmt = stmt.where(Product.price_inr > constraints.price_min)
    if constraints.price_max is not None:
        if constraints.price_max_inclusive:
            stmt = stmt.where(Product.price_inr <= constraints.price_max)
        else:
            stmt = stmt.where(Product.price_inr < constraints.price_max)
    return stmt
