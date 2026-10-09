"""Provider-neutral fashion constraint extraction with deterministic fallback."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from fashion_search.catalog.generator import COLORS, PROFILES
from fashion_search.ai.factory import get_generation_provider
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.generation.base import GenerationProvider
from fashion_search.prompts import load_prompt
from fashion_search.search.schemas import (
    ConstraintParseResponse,
    FashionSearchConstraints,
)

logger = get_logger(__name__)

CATEGORIES = frozenset(profile.category for profile in PROFILES)
# Search vocabulary includes explicit milestone colors that are valid product metadata
# even though the current deterministic seed palette does not generate all of them.
COLORS_SUPPORTED = frozenset((*COLORS, "red", "blue", "gray", "purple"))
OCCASIONS = frozenset(
    occasion for profile in PROFILES for occasion in profile.occasions
)
SIZES = frozenset(size for profile in PROFILES for size in profile.sizes)
_SIZE_PATTERN = "|".join(
    re.escape(size).replace(r"\ ", r"\s+")
    for size in sorted(SIZES, key=len, reverse=True)
)
GENDERS = frozenset(gender for profile in PROFILES for gender in profile.genders)

CATEGORY_ALIASES = {
    "tee": "t-shirt",
    "tees": "t-shirt",
    "t shirt": "t-shirt",
    "t shirts": "t-shirt",
    "tshirt": "t-shirt",
    "tshirts": "t-shirt",
    "trainer": "footwear",
    "trainers": "footwear",
    "sneaker": "footwear",
    "sneakers": "footwear",
    "kurti": "kurta",
    "kurtis": "kurta",
    "running shoe": "footwear",
    "running shoes": "footwear",
    "sarees": "saree",
    "shirts": "shirt",
    "dresses": "dress",
}
COLOR_ALIASES = {"navy": "navy blue", "grey": "gray"}
GENDER_ALIASES = {
    "male": "men",
    "man": "men",
    "men's": "men",
    "mens": "men",
    "female": "women",
    "woman": "women",
    "women's": "women",
    "womens": "women",
    "boy": "kids",
    "boys": "kids",
    "girl": "kids",
    "girls": "kids",
}
OCCASION_ALIASES = {"work": "office", "college": "casual"}


@dataclass(frozen=True)
class PriceFacts:
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    minimum_inclusive: bool | None = None
    maximum_inclusive: bool | None = None
    detected: bool = False
    invalid: bool = False


def _phrase_pattern(phrase: str) -> str:
    parts = [re.escape(part) for part in re.split(r"[\s-]+", phrase) if part]
    return r"(?<!\w)" + r"[\s-]+".join(parts) + r"(?!\w)"


def _find_term(
    query: str, values: set[str] | frozenset[str], aliases: dict[str, str]
) -> str | None:
    candidates = {value: value for value in values}
    candidates.update(aliases)
    for phrase in sorted(candidates, key=len, reverse=True):
        if re.search(_phrase_pattern(phrase), query, flags=re.IGNORECASE):
            canonical = candidates[phrase]
            return canonical if canonical in values else None
    return None


def normalize_constraints(
    value: FashionSearchConstraints, *, currency: str = "INR"
) -> FashionSearchConstraints:
    """Normalize known aliases and safely discard unsupported categorical values."""

    def normalized(
        raw: str | None, supported: frozenset[str], aliases: dict[str, str]
    ) -> str | None:
        if raw is None:
            return None
        cleaned = re.sub(r"\s+", " ", raw.strip().lower().replace("_", " "))
        canonical = aliases.get(cleaned, cleaned)
        return canonical if canonical in supported else None

    size = value.size.strip() if value.size else None
    if size:
        size = (
            "Free Size"
            if size.lower().replace("-", " ") == "free size"
            else size.upper()
        )
        if size not in SIZES:
            size = None
    return FashionSearchConstraints(
        category=normalized(value.category, CATEGORIES, CATEGORY_ALIASES),
        color=normalized(value.color, COLORS_SUPPORTED, COLOR_ALIASES),
        occasion=normalized(value.occasion, OCCASIONS, OCCASION_ALIASES),
        size=size,
        gender=normalized(value.gender, GENDERS, GENDER_ALIASES),
        price_min=value.price_min,
        price_max=value.price_max,
        currency=currency.upper(),
        price_min_inclusive=value.price_min_inclusive,
        price_max_inclusive=value.price_max_inclusive,
    )


_AMOUNT = r"(?P<{name}>-?\d[\d,]*(?:\.\d+)?)\s*(?P<{name}_k>k)?"
_CURRENCY = r"(?:₹|rs\.?|inr|rupees?)?\s*"


def _amount(match: re.Match[str], name: str) -> Decimal | None:
    try:
        value = Decimal(match.group(name).replace(",", ""))
        if match.group(f"{name}_k"):
            value *= 1000
        return value
    except (InvalidOperation, AttributeError):
        return None


def parse_price_facts(query: str) -> PriceFacts:
    """Parse explicit INR bounds only; approximate prices intentionally produce no bounds."""
    text = query.lower()
    if re.search(r"\b(?:around|about|approximately|approx)\b", text):
        return PriceFacts()

    range_pattern = re.compile(
        rf"\b(?:between|from)\s+{_CURRENCY}{_AMOUNT.format(name='low')}\s+"
        rf"(?:and|to|-)\s+{_CURRENCY}{_AMOUNT.format(name='high')}",
        re.IGNORECASE,
    )
    range_match = range_pattern.search(text)
    if range_match:
        low, high = _amount(range_match, "low"), _amount(range_match, "high")
        remaining = text[: range_match.start()] + text[range_match.end() :]
        has_extra_bound = (
            re.search(
                r"\b(?:under|below|less\s+than|up\s+to|at\s+most|above|over|"
                r"more\s+than|at\s+least|minimum|maximum|min|max)\b",
                remaining,
            )
            is not None
        )
        invalid = (
            low is None
            or high is None
            or low < 0
            or high < 0
            or low > high
            or has_extra_bound
        )
        return PriceFacts(low, high, True, True, detected=True, invalid=invalid)

    bounds: list[tuple[str, Decimal | None, bool]] = []
    patterns = (
        (
            "max",
            False,
            rf"\b(?:under|below|less\s+than)\s+{_CURRENCY}{_AMOUNT.format(name='amount')}",
        ),
        (
            "max",
            True,
            rf"\b(?:up\s+to|at\s+most|maximum|max)\s+{_CURRENCY}{_AMOUNT.format(name='amount')}",
        ),
        (
            "min",
            False,
            rf"\b(?:above|over|more\s+than)\s+{_CURRENCY}{_AMOUNT.format(name='amount')}",
        ),
        (
            "min",
            True,
            rf"\b(?:at\s+least|minimum|min)\s+{_CURRENCY}{_AMOUNT.format(name='amount')}",
        ),
    )
    for kind, inclusive, pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            bounds.append((kind, _amount(match, "amount"), inclusive))
    if not bounds:
        return PriceFacts()
    if any(value is None or value < 0 for _, value, _ in bounds):
        return PriceFacts(detected=True, invalid=True)
    mins = [(value, inclusive) for kind, value, inclusive in bounds if kind == "min"]
    maxes = [(value, inclusive) for kind, value, inclusive in bounds if kind == "max"]
    if len(mins) > 1 or len(maxes) > 1:
        return PriceFacts(detected=True, invalid=True)
    minimum, min_inc = mins[0] if mins else (None, None)
    maximum, max_inc = maxes[0] if maxes else (None, None)
    invalid = minimum is not None and maximum is not None and minimum > maximum
    return PriceFacts(
        minimum, maximum, min_inc, max_inc, detected=True, invalid=invalid
    )


def fallback_parse(query: str, *, currency: str = "INR") -> FashionSearchConstraints:
    """Extract a deliberately small set of explicit constraints without an LLM."""
    text = query.strip().lower()
    # A narrow guard for common prompt-injection phrasing; the remaining query is
    # still parsed as ordinary data and the original query is always preserved.
    text = re.sub(r"\b(?:ignore|disregard)\b[^;.!?]*(?:[;.!?]|$)", " ", text)
    price = parse_price_facts(text)
    size = None
    size_match = re.search(rf"\bsize\s*[:=-]?\s*({_SIZE_PATTERN})\b", text, re.I)
    if size_match:
        size = size_match.group(1)
    raw = FashionSearchConstraints(
        category=_find_term(text, CATEGORIES, CATEGORY_ALIASES),
        color=_find_term(text, COLORS_SUPPORTED, COLOR_ALIASES),
        occasion=_find_term(text, OCCASIONS, OCCASION_ALIASES),
        size=size,
        gender=_find_term(text, GENDERS, GENDER_ALIASES),
        price_min=None if price.invalid else price.minimum,
        price_max=None if price.invalid else price.maximum,
        currency=currency,
        price_min_inclusive=None if price.invalid else price.minimum_inclusive,
        price_max_inclusive=None if price.invalid else price.maximum_inclusive,
    )
    return normalize_constraints(raw, currency=currency)


class ConstraintExtractor:
    """Use configured structured generation, then deterministic parsing on failure."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
        provider: GenerationProvider | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client
        if provider is not None:
            self._provider = provider
        elif client is not None:
            self._provider = get_generation_provider(self._settings, client=client)
        else:
            from fashion_search.generation.router import GenerationRouter

            self._provider = GenerationRouter(settings=self._settings)

    def _gemini_extract(self, query: str) -> FashionSearchConstraints:
        """Legacy method name retained for callers/tests; implementation is neutral."""
        return self._provider.generate_structured(
            f"Fashion search query (data only): {query}",
            FashionSearchConstraints,
            system_prompt=load_prompt("system_query_parse"),
        )

    def extract(self, query: str) -> ConstraintParseResponse:
        cleaned = query.strip()
        started = time.perf_counter()
        method = self._provider.name
        try:
            constraints = normalize_constraints(
                self._gemini_extract(cleaned), currency=self._settings.market_currency
            )
        except Exception as exc:
            method = "fallback"
            logger.warning(
                "constraint_provider_failed provider=%s query_len=%s error_type=%s",
                self._provider.name,
                len(cleaned),
                type(exc).__name__,
            )
            constraints = fallback_parse(
                cleaned, currency=self._settings.market_currency
            )

        explicit_price = parse_price_facts(cleaned)
        if explicit_price.detected:
            generated_price = (
                constraints.price_min,
                constraints.price_max,
                constraints.price_min_inclusive,
                constraints.price_max_inclusive,
            )
            deterministic_price = (
                (
                    explicit_price.minimum,
                    explicit_price.maximum,
                    explicit_price.minimum_inclusive,
                    explicit_price.maximum_inclusive,
                )
                if not explicit_price.invalid
                else (None, None, None, None)
            )
            if generated_price != deterministic_price:
                logger.warning(
                    "constraint_price_disagreement query_len=%s method=%s invalid=%s",
                    len(cleaned),
                    method,
                    explicit_price.invalid,
                )
                payload = constraints.model_dump()
                payload.update(
                    price_min=deterministic_price[0],
                    price_max=deterministic_price[1],
                    price_min_inclusive=deterministic_price[2],
                    price_max_inclusive=deterministic_price[3],
                )
                constraints = FashionSearchConstraints.model_validate(payload)

        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "constraint_extraction method=%s query_len=%s latency_ms=%.1f",
            method,
            len(cleaned),
            elapsed_ms,
        )
        return ConstraintParseResponse(
            query=cleaned, constraints=constraints, extraction_method=method
        )


def _is_transient(exc: Exception) -> bool:
    value = f"{type(exc).__name__} {exc}".lower()
    return any(
        token in value
        for token in (
            "timeout",
            "429",
            "rate",
            "quota",
            "500",
            "503",
            "unavailable",
            "connection",
        )
    )


def parse_constraints(
    query: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    provider: GenerationProvider | None = None,
) -> ConstraintParseResponse:
    """Service entry point used by the API and semantic-search callers."""
    return ConstraintExtractor(
        settings=settings, client=client, provider=provider
    ).extract(query)


# Backward-compatible import; new business code uses ConstraintExtractor.
GeminiConstraintExtractor = ConstraintExtractor
