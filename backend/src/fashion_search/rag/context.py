"""Allowlisted and bounded RAG context from already retrieved products."""

from __future__ import annotations

import json
import re
from typing import Any

from fashion_search.search.schemas import HybridSearchResult


def _clean(value: Any, max_chars: int | None = None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text[:max_chars].rstrip() if max_chars else text


def build_retrieval_context(
    products: list[HybridSearchResult],
    *,
    top_k: int = 5,
    description_max_chars: int = 360,
) -> list[dict[str, Any]]:
    """Build compact context from the ranked, exact-filtered product results only."""
    if top_k < 1 or description_max_chars < 1:
        raise ValueError("context bounds must be positive")
    context: list[dict[str, Any]] = []
    for product in products[:top_k]:
        row: dict[str, Any] = {
            "reference": f"product_{product.product_id}",
            "product_id": product.product_id,
            "title": _clean(product.title),
            "category": _clean(product.category),
            "color": _clean(product.color),
            "material": _clean(product.material),
            "style": _clean(product.style),
            "occasion": _clean(product.occasion),
            "gender": _clean(product.gender),
            "price_inr": product.price_inr,
            "sizes": [_clean(size) for size in product.sizes if _clean(size)],
            "description": _clean(product.description, description_max_chars),
        }
        # Future catalog extensions can provide these; absent attributes stay absent.
        for optional_field in ("brand", "fit"):
            value = _clean(getattr(product, optional_field, None))
            if value:
                row[optional_field] = value
        context.append(
            {key: value for key, value in row.items() if value not in (None, "", [])}
        )
    return context


def context_size_chars(context: list[dict[str, Any]]) -> int:
    """Return the serialized context length for stable operational telemetry."""
    return len(json.dumps(context, ensure_ascii=False, separators=(",", ":")))
