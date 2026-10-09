"""Deterministic, structured-field-grounded ranking explanations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from fashion_search.search.ranking import RankedCandidate
from fashion_search.search.schemas import FashionSearchConstraints


class ProductMetadata(Protocol):
    category: str
    color: str
    occasion: str | None
    sizes: list[str]
    gender: str
    price_inr: int


def _same(actual: str | None, expected: str | None) -> bool:
    return (
        actual is not None
        and expected is not None
        and actual.casefold() == expected.casefold()
    )


def matches_category(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    return _same(product.category, constraints.category)


def matches_color(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    return _same(product.color, constraints.color)


def matches_occasion(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    return _same(product.occasion, constraints.occasion)


def matches_size(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    return constraints.size is not None and constraints.size in (product.sizes or [])


def matches_gender(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    return _same(product.gender, constraints.gender)


def matches_price(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    price = Decimal(product.price_inr)
    if constraints.price_min is not None:
        if constraints.price_min_inclusive and price < constraints.price_min:
            return False
        if not constraints.price_min_inclusive and price <= constraints.price_min:
            return False
    if constraints.price_max is not None:
        if constraints.price_max_inclusive and price > constraints.price_max:
            return False
        if not constraints.price_max_inclusive and price >= constraints.price_max:
            return False
    return constraints.price_min is not None or constraints.price_max is not None


MATCHERS = (
    ("category", matches_category),
    ("color", matches_color),
    ("occasion", matches_occasion),
    ("size", matches_size),
    ("gender", matches_gender),
    ("price", matches_price),
)


def matched_constraints(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> list[str]:
    """Return only explicit constraints verified against structured metadata."""
    return [name for name, matcher in MATCHERS if matcher(product, constraints)]


def all_hard_constraints_match(
    product: ProductMetadata, constraints: FashionSearchConstraints
) -> bool:
    active = {
        "category": constraints.category is not None,
        "color": constraints.color is not None,
        "occasion": constraints.occasion is not None,
        "size": constraints.size is not None,
        "gender": constraints.gender is not None,
        "price": constraints.price_min is not None or constraints.price_max is not None,
    }
    matched = set(matched_constraints(product, constraints))
    return all(not enabled or name in matched for name, enabled in active.items())


def _money(value: Decimal | int) -> str:
    number = Decimal(value)
    if number == number.to_integral():
        return f"₹{int(number):,}"
    return f"₹{number:,.2f}"


@dataclass(frozen=True)
class QualityThresholds:
    strong_semantic: float = 0.75
    weak_semantic: float = 0.35
    min_keyword: float = 0.01


def classify_match_quality(
    product: ProductMetadata,
    constraints: FashionSearchConstraints,
    ranked: RankedCandidate,
    thresholds: QualityThresholds,
) -> str:
    """Classify using hard-filter validity and configured retrieval signals."""
    if not all_hard_constraints_match(product, constraints):
        return "weak"
    semantic = ranked.semantic_similarity
    keyword_ok = (
        ranked.keyword_rank_score is not None
        and ranked.keyword_rank_score >= thresholds.min_keyword
    )
    both = ranked.semantic_rank is not None and ranked.keyword_rank is not None
    if (
        both
        and keyword_ok
        and semantic is not None
        and semantic >= thresholds.weak_semantic
    ):
        return "strong"
    if semantic is not None and semantic >= thresholds.strong_semantic:
        return "strong"
    if (
        both
        or keyword_ok
        or (semantic is not None and semantic >= thresholds.weak_semantic)
    ):
        return "good"
    return "weak"


class MatchExplanationBuilder:
    """Build concise explanations without an LLM or description inference."""

    def build(
        self,
        product: ProductMetadata,
        constraints: FashionSearchConstraints,
        ranked: RankedCandidate,
        quality: str,
    ) -> str:
        matched = set(matched_constraints(product, constraints))
        attributes: list[str] = []
        if "color" in matched and "category" in matched:
            attributes.append(f"{constraints.color} {constraints.category}")
        elif "category" in matched:
            attributes.append(str(constraints.category))
        elif "color" in matched:
            attributes.append(str(constraints.color))
        if "occasion" in matched:
            attributes.append(f"{constraints.occasion}-wear")
        if "size" in matched:
            attributes.append(f"size {constraints.size}")
        if "gender" in matched:
            attributes.append(f"{constraints.gender}'s")

        sentences: list[str] = []
        if attributes:
            sentences.append(f"Matches your {' and '.join(attributes)} requirements")

        if "price" in matched:
            price = _money(product.price_inr)
            if constraints.price_min is not None and constraints.price_max is not None:
                detail = f"{price}, within your {_money(constraints.price_min)}–{_money(constraints.price_max)} range"
            elif constraints.price_max is not None:
                relation = "within" if constraints.price_max_inclusive else "below"
                detail = (
                    f"{price}, {relation} your {_money(constraints.price_max)} budget"
                )
            else:
                relation = "meeting" if constraints.price_min_inclusive else "above"
                detail = (
                    f"{price}, {relation} your {_money(constraints.price_min)} minimum"
                )
            if sentences:
                sentences[0] += f" and costs {detail}"
            else:
                sentences.append(f"Costs {detail}")

        if sentences:
            sentences[0] += "."

        both = ranked.semantic_rank is not None and ranked.keyword_rank is not None
        prefix = "It also" if sentences else "This product"
        if both and quality != "weak":
            signal = f"{prefix} has keyword and semantic relevance to your search."
        elif ranked.keyword_rank is not None and quality != "weak":
            signal = f"{prefix} matches keywords in your search."
        elif ranked.semantic_rank is not None and quality != "weak":
            signal = f"{prefix} ranked highly for semantic relevance."
        else:
            signal = "Overall search relevance is limited."
        sentences.append(signal)
        return " ".join(sentences)
