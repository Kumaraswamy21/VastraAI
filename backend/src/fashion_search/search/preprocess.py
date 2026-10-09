"""Deterministic retrieval-query preparation for hybrid search."""

from __future__ import annotations

import re

from fashion_search.search.constraints import (
    CATEGORY_ALIASES,
    GENDER_ALIASES,
    OCCASION_ALIASES,
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
    if (
        price.detected
        and not price.invalid
        and (constraints.price_min is not None or constraints.price_max is not None)
    ):
        result = _PRICE_FRAGMENT.sub(" ", result)
        result = re.sub(r"\s+", " ", result).strip(" ,.")

    if constraints.gender is not None:
        result = _strip_phrases(result, _GENDER_PHRASES)
        # Drop dangling connectors left by "shirt for men" -> "shirt for".
        result = re.sub(
            r"\b(?:for|at|on|during)\s*$",
            "",
            result,
            flags=re.IGNORECASE,
        ).strip(" ,.")

    if constraints.occasion is not None:
        # Only strip aliases that map to the extracted occasion.
        occasion_phrases = {constraints.occasion} | {
            alias
            for alias, canonical in OCCASION_ALIASES.items()
            if canonical == constraints.occasion
        }
        result = _strip_phrases(result, occasion_phrases)
        result = re.sub(
            r"\b(?:for|at|on|during)\s*$",
            "",
            result,
            flags=re.IGNORECASE,
        ).strip(" ,.")

    if constraints.size is not None:
        size = constraints.size
        size_phrases = {size, f"size {size}", f"size: {size}"}
        if size == "Free Size":
            size_phrases.add("free size")
        result = _strip_phrases(result, size_phrases)

    # The parser normalizes category aliases, but FTS needs the indexed category
    # term. Otherwise "black tee" searches for "tee" although rows say t-shirt.
    if constraints.category is not None:
        for alias, canonical in sorted(
            CATEGORY_ALIASES.items(), key=lambda item: -len(item[0])
        ):
            if canonical == constraints.category:
                result = _phrase_pattern(alias).sub(canonical, result)

    result = re.sub(
        r"\b(?:for|at|on|during)\s*$", "", result, flags=re.IGNORECASE
    ).strip(" ,.")

    # If stripping removed everything, fall back to category/color or original.
    if not result:
        for value in (constraints.category, constraints.color):
            if value:
                return value
        return cleaned
    return result
