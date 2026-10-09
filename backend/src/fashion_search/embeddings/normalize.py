"""Deterministic provider-neutral product text for document embeddings."""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any, Mapping

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# Attribute labels emitted after the title, in fixed order.
_ATTRIBUTE_KEYS: tuple[tuple[str, str], ...] = (
    ("category", "Category"),
    ("color", "Color"),
    ("material", "Material"),
    ("style", "Style"),
    ("occasion", "Occasion"),
    ("gender", "Gender"),
)


def clean_text(value: Any) -> str | None:
    """Return stripped plain text, or None when the value is empty."""
    if value is None:
        return None
    text = html.unescape(str(value))
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def _title_line(product: Mapping[str, Any]) -> str | None:
    """Build the leading title sentence without inventing a brand."""
    title = clean_text(product.get("title"))
    brand = clean_text(product.get("brand"))
    if brand and title:
        if brand.lower() in title.lower():
            return f"{title}."
        return f"{brand} {title}."
    if title:
        return f"{title}."
    if brand:
        return f"{brand}."
    return None


def normalize_product_text(product: Mapping[str, Any]) -> str:
    """Convert a product mapping into deterministic embedding-ready text.

    Excludes price, stock, IDs, sizes, and image references. Uses only
    attributes present on the record; never invents missing fields.
    """
    parts: list[str] = []
    title_line = _title_line(product)
    if title_line:
        parts.append(title_line)

    seen_values: set[str] = set()
    if title_line:
        seen_values.add(title_line.rstrip(".").lower())

    for key, label in _ATTRIBUTE_KEYS:
        value = clean_text(product.get(key))
        if value is None:
            continue
        lowered = value.lower()
        if lowered in seen_values:
            continue
        seen_values.add(lowered)
        parts.append(f"{label}: {value}.")

    description = clean_text(product.get("description"))
    if description is not None:
        lowered = description.lower()
        if lowered not in seen_values:
            parts.append(
                description if description.endswith(".") else f"{description}."
            )

    return " ".join(parts)


def text_hash(text: str) -> str:
    """Return a hex SHA-256 digest of normalized embedding text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
