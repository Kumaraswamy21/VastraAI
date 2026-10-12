"""API request and response shapes for live Shopify catalog results."""

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)

from fashion_search.search.schemas import ActiveFilter, SearchState


class ShopifySearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=10)


class ShopifyProductResult(BaseModel):
    product_id: str
    title: str
    description: str | None = None
    product_url: str | None = None
    image_url: AnyHttpUrl | None = None
    image_alt: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    merchant_name: str | None = None
    merchant_domain: str | None = None
    merchant_url: str | None = None
    available: bool | None = None
    variants: list[dict[str, Any]] | None = None


class ShopifySearchResponse(BaseModel):
    query: str
    total: int = Field(ge=0)
    results: list[ShopifyProductResult]
    has_next_page: bool = False


class ShopifyConversationalSearchResponse(ShopifySearchResponse):
    """Search state and grounded answer; product data remains response-only."""

    session_id: str
    revision: int
    interpreted_as: Literal["initial", "refinement", "new_search"]
    state: SearchState
    active_filters: list[ActiveFilter]
    answer: str | None = None
    referenced_product_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


def map_shopify_product(raw: dict[str, Any]) -> ShopifyProductResult | None:
    """Adapt one live UCP product to the Shopify response shape."""
    product_id = raw.get("id")
    title = raw.get("title")
    variants = raw.get("variants")
    variants = variants if isinstance(variants, list) else []
    first_variant = next((item for item in variants if isinstance(item, dict)), {})
    product_url = raw.get("url") or first_variant.get("url")
    if not isinstance(product_id, str) or not product_id.strip():
        return None
    if not isinstance(title, str) or not title.strip():
        return None
    if product_url is not None and not _valid_http_url(product_url):
        return None

    price_range = raw.get("price_range")
    price_range = price_range if isinstance(price_range, dict) else {}
    minimum = price_range.get("min")
    minimum = minimum if isinstance(minimum, dict) else {}
    maximum = price_range.get("max")
    maximum = maximum if isinstance(maximum, dict) else {}
    variant_price = first_variant.get("price")
    variant_price = variant_price if isinstance(variant_price, dict) else {}
    minimum_amount = minimum.get("amount", variant_price.get("amount"))
    maximum_amount = maximum.get("amount", minimum_amount)
    currency = minimum.get("currency", variant_price.get("currency"))
    if not isinstance(currency, str) or len(currency) != 3:
        currency = None
    else:
        currency = currency.upper()
    price_min = _major_units(minimum_amount, currency)
    max_currency = maximum.get("currency", currency)
    price_max = (
        _major_units(maximum_amount, max_currency.upper())
        if isinstance(max_currency, str) and len(max_currency) == 3
        else None
    )
    if max_currency and currency and max_currency.upper() != currency:
        price_max = None

    media = raw.get("media") or []
    image = next(
        (
            item
            for item in media
            if isinstance(item, dict)
            and item.get("type") == "image"
            and isinstance(item.get("url"), str)
        ),
        None,
    )
    description = raw.get("description")
    description = description if isinstance(description, dict) else {}
    description_text = description.get("plain") or description.get("html")
    if isinstance(description_text, str):
        import re
        from html import unescape

        description_text = unescape(re.sub(r"<[^>]*>", " ", description_text))
        description_text = " ".join(description_text.split()) or None
    else:
        description_text = None
    seller = raw.get("seller")
    if not isinstance(seller, dict):
        seller = next(
            (
                item.get("seller")
                for item in variants
                if isinstance(item, dict) and isinstance(item.get("seller"), dict)
            ),
            {},
        )
    availability_values = [
        item.get("availability", {}).get("available")
        for item in variants
        if isinstance(item, dict) and isinstance(item.get("availability"), dict)
    ]
    availability_values = [
        value for value in availability_values if isinstance(value, bool)
    ]
    available = (
        (any(availability_values) if True in availability_values else False)
        if availability_values
        else None
    )
    valid_variants = [item for item in variants if isinstance(item, dict)]

    try:
        return ShopifyProductResult(
            product_id=product_id,
            title=title,
            description=description_text[:1500] if description_text else None,
            product_url=product_url,
            image_url=image.get("url") if image else None,
            image_alt=image.get("alt_text") if image else None,
            price_min=price_min,
            price_max=price_max,
            currency=currency,
            merchant_name=_optional_text(seller.get("name")),
            merchant_domain=_optional_text(seller.get("domain")),
            merchant_url=seller.get("url")
            if _valid_http_url(seller.get("url"))
            else None,
            available=available,
            variants=valid_variants or None,
        )
    except (ValidationError, ValueError, TypeError):
        return None


def map_shopify_products(raw_products: object) -> list[ShopifyProductResult]:
    """Map a response's products array, skipping malformed product entries."""
    if not isinstance(raw_products, list):
        return []
    return [
        mapped
        for raw in raw_products
        if isinstance(raw, dict)
        if (mapped := map_shopify_product(raw)) is not None
    ]


def _valid_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        TypeAdapter(AnyHttpUrl).validate_python(value)
    except ValidationError:
        return False
    return True


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _major_units(amount: object, currency: str | None) -> Decimal | None:
    if currency is None or isinstance(amount, bool) or amount is None:
        return None
    # Shopify prices use ISO currency minor units (for example, cents/paise).
    zero_decimal = {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "ISK",
        "JPY",
        "KMF",
        "KRW",
        "PYG",
        "RWF",
        "UGX",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
    three_decimal = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}
    exponent = 0 if currency in zero_decimal else 3 if currency in three_decimal else 2
    try:
        value = Decimal(str(amount))
        return value / (Decimal(10) ** exponent) if value.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None
