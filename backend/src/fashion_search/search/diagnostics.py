"""Single-query diagnostics for searches eliminated by hard filters."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fashion_search.catalog.models import Product
from fashion_search.core.db import get_engine
from fashion_search.search.filters import apply_search_constraints
from fashion_search.search.schemas import FashionSearchConstraints, SearchDiagnostics


FILTER_ORDER = ("category", "color", "price", "occasion", "size", "gender")


def _active(constraints: FashionSearchConstraints, name: str) -> bool:
    if name == "price":
        return constraints.price_min is not None or constraints.price_max is not None
    return getattr(constraints, name) is not None


def _only(constraints: FashionSearchConstraints, names: set[str]) -> FashionSearchConstraints:
    payload: dict[str, object] = {"currency": constraints.currency}
    for name in ("category", "color", "occasion", "size", "gender"):
        if name in names:
            payload[name] = getattr(constraints, name)
    if "price" in names:
        payload.update(
            price_min=constraints.price_min,
            price_max=constraints.price_max,
            price_min_inclusive=constraints.price_min_inclusive,
            price_max_inclusive=constraints.price_max_inclusive,
        )
    return FashionSearchConstraints.model_validate(payload)


def _count_expr(constraints: FashionSearchConstraints):
    statement = apply_search_constraints(select(func.count(Product.id)), constraints)
    return statement.scalar_subquery()


def diagnose_zero_results(constraints: FashionSearchConstraints) -> tuple[SearchDiagnostics, list[str]]:
    """Get progressive and leave-one-out counts with one database round trip."""
    active = [name for name in FILTER_ORDER if _active(constraints, name)]
    columns = [_count_expr(_only(constraints, set())).label("initial_catalog")]
    accumulated: set[str] = set()
    for name in active:
        accumulated.add(name)
        columns.append(_count_expr(_only(constraints, accumulated)).label(f"after_{name}"))
    for name in active:
        columns.append(
            _count_expr(_only(constraints, set(active) - {name})).label(f"without_{name}")
        )

    with Session(get_engine()) as session:
        row = session.execute(select(*columns)).one()._mapping

    counts = {name: int(row[f"after_{name}"]) for name in active}
    exact_match_count = counts[active[-1]] if active else int(row["initial_catalog"])
    eliminated_by = None
    previous = int(row["initial_catalog"])
    for name in active:
        current = counts[name]
        if previous > 0 and current == 0:
            eliminated_by = name
            break
        previous = current

    suggestions = []
    if exact_match_count == 0:
        for name in active:
            if int(row[f"without_{name}"]) > 0:
                suggestions.append(
                    f"Products are available if the {name} filter is removed."
                )
    return (
        SearchDiagnostics(
            initial_catalog=int(row["initial_catalog"]),
            exact_match_count=exact_match_count,
            filter_counts=counts,
            eliminated_by=eliminated_by,
        ),
        suggestions,
    )
