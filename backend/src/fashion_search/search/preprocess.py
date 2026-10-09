"""Deterministic retrieval-query preparation for hybrid search."""

from __future__ import annotations

import re

from fashion_search.search.constraints import parse_price_facts
from fashion_search.search.schemas import FashionSearchConstraints

_PRICE_FRAGMENT = re.compile(
    r"\b(?:between|from)\s+(?:₹|rs\.?|inr|rupees?\s*)?[\d,]+(?:\.\d+)?\s*k?\s+"
    r"(?:and|to|-)\s+(?:₹|rs\.?|inr|rupees?\s*)?[\d,]+(?:\.\d+)?\s*k?\b"
    r"|"
    r"\b(?:under|below|less\s+than|up\s+to|at\s+most|maximum|max|"
    r"above|over|more\s+than|at\s+least|minimum|min)\s+"
    r"(?:₹|rs\.?|inr|rupees?\s*)?[\d,]+(?:\.\d+)?\s*k?\b",
    flags=re.IGNORECASE,
)


def build_retrieval_query(
    query: str,
    constraints: FashionSearchConstraints,
) -> str:
    """Remove reliably extracted price text; preserve other product meaning."""
    cleaned = (query or "").strip()
    if not cleaned:
        return cleaned
    price = parse_price_facts(cleaned)
    if not price.detected or price.invalid:
        return cleaned
    if constraints.price_min is None and constraints.price_max is None:
        return cleaned
    without_price = _PRICE_FRAGMENT.sub(" ", cleaned)
    without_price = re.sub(r"\s+", " ", without_price).strip(" ,.")
    return without_price or cleaned
