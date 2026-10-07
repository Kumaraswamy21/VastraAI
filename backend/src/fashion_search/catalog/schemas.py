"""Pydantic shapes for catalog products and extracted search filters."""

from pydantic import BaseModel, Field, HttpUrl


class ProductRecord(BaseModel):
    """Public product card returned to the shopper."""

    id: str
    title: str
    brand: str
    category: str
    color: str
    occasion: str
    price_inr: int = Field(ge=0)
    currency: str = "INR"
    product_url: HttpUrl
    image_url: HttpUrl
    description: str = ""


class ProductFilters(BaseModel):
    """Structured filters parsed from a natural-language shopping query."""

    color: str | None = None
    category: str | None = None
    occasion: str | None = None
    max_price_inr: int | None = Field(default=None, ge=0)
    brand: str | None = None
    query_text: str | None = None
