"""Request and response shapes for product search."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FashionSearchConstraints(BaseModel):
    """Validated, metadata-compatible constraints extracted from a query."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: str | None = None
    color: str | None = None
    occasion: str | None = None
    size: str | None = None
    gender: str | None = None
    price_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    price_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    price_min_inclusive: bool | None = None
    price_max_inclusive: bool | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_price_bounds(self) -> "FashionSearchConstraints":
        if self.price_min is not None and self.price_max is not None:
            if self.price_min > self.price_max:
                raise ValueError("price_min cannot be greater than price_max")
        if self.price_min is None:
            self.price_min_inclusive = None
        elif self.price_min_inclusive is None:
            self.price_min_inclusive = True
        if self.price_max is None:
            self.price_max_inclusive = None
        elif self.price_max_inclusive is None:
            self.price_max_inclusive = True
        return self


class ConstraintParseRequest(BaseModel):
    """Natural-language query accepted by the constraint parser."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value.strip()


class ConstraintParseResponse(BaseModel):
    """Original query plus extracted constraints; no filters are applied here."""

    query: str
    constraints: FashionSearchConstraints
    extraction_method: Literal["gemini", "fallback"]


class SemanticSearchRequest(BaseModel):
    """Natural-language semantic search request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value.strip()


class SemanticSearchHit(BaseModel):
    """One ranked product from cosine similarity search."""

    product_id: int
    title: str
    category: str
    color: str
    material: str
    style: str
    gender: str
    occasion: str
    price_inr: int
    currency: str = "INR"
    image_reference: str
    product_url: str
    similarity_score: float = Field(ge=-1.0, le=1.0)


class SemanticSearchResponse(BaseModel):
    """Ranked semantic search payload."""

    query: str
    total: int = Field(ge=0)
    embedding_model: str
    embedding_dimensions: int
    results: list[SemanticSearchHit]
