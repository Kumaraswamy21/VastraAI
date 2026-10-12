"""Deterministic retrieval-query preparation for hybrid search."""

from __future__ import annotations

import re

from fashion_search.search.constraints import (
    CATEGORY_ALIASES,
    CATEGORIES,
    COLOR_ALIASES,
    COLORS_SUPPORTED,
    GENDER_ALIASES,
    OCCASION_ALIASES,
    OCCASIONS,
    SIZES,
    parse_price_facts,
)
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

# Gender and occasion are hard-filtered in SQL but are not part of the weighted
# search_vector (title/category/color/material/style/description). Leaving them
# in websearch_to_tsquery forces AND matches that eliminate valid products.
_GENDER_PHRASES = frozenset(
    {
        "men",
        "women",
        "unisex",
        "kids",
        *GENDER_ALIASES.keys(),
        *GENDER_ALIASES.values(),
    }
)


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in re.split(r"[\s-]+", phrase) if part]
    return re.compile(
        r"(?<!\w)" + r"[\s-]+".join(parts) + r"(?!\w)", flags=re.IGNORECASE
    )


def _strip_phrases(text: str, phrases: set[str] | frozenset[str]) -> str:
    updated = text
    for phrase in sorted(phrases, key=len, reverse=True):
        if not phrase:
            continue
        updated = _phrase_pattern(phrase).sub(" ", updated)
    return re.sub(r"\s+", " ", updated).strip(" ,.")


def build_retrieval_query(
    query: str,
    constraints: FashionSearchConstraints,
) -> str:
    """Strip extracted price and non-indexed hard-filter phrasing for retrieval.

    Category/color remain because they are present in ``search_vector``. Gender
    and occasion are applied as SQL filters only and must not AND-fail FTS.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        return cleaned

    result = cleaned
    price = parse_price_facts(cleaned)
    if price.detected and not price.invalid:
        result = _PRICE_FRAGMENT.sub(" ", result)
        result = re.sub(r"\s+", " ", result).strip(" ,.")

    # SearchState keeps the original natural-language query across refinements.
    # Remove every recognized hard-filter phrase before keyword retrieval so
    # stale values (e.g. "black" after changing to blue) cannot veto new filters.
    occasion_phrases = set(OCCASIONS)
    occasion_phrases.update(
        alias
        for alias, canonical in OCCASION_ALIASES.items()
        if canonical == constraints.occasion
    )
    facet_phrases = (
        set(CATEGORIES)
        | set(CATEGORY_ALIASES)
        | set(COLORS_SUPPORTED)
        | set(COLOR_ALIASES)
        | occasion_phrases
        | set(SIZES)
        | set(_GENDER_PHRASES)
    )
    facet_phrases |= {f"size {size}" for size in SIZES}
    result = _strip_phrases(result, facet_phrases)
    result = re.sub(
        r"\b(?:for|at|on|during)\s+(?:a|an|the)\s*$",
        "",
        result,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        r"\b(?:for|at|on|during)\s*$", "", result, flags=re.IGNORECASE
    ).strip(" ,.")
    result = re.sub(
        r"^(?:a|an|the)\s+|\s+(?:a|an|the)$", "", result, flags=re.IGNORECASE
    )

    # Category and color are indexed in PostgreSQL FTS, so add only their
    # currently authoritative values back after stale terms have been removed.
    indexed_facets = [constraints.color, constraints.category]
    result = " ".join([result, *(value for value in indexed_facets if value)]).strip()

    # If stripping removed everything, fall back to category/color or original.
    if not result:
        for value in (constraints.category, constraints.color):
            if value:
                return value
        return cleaned
    return result
