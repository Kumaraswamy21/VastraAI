"""Pydantic shapes for catalog products and extracted search filters."""

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class ProductCreate(BaseModel):
    """Validated catalog row accepted by the deterministic seed loader."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=3, max_length=255)
    category: str = Field(min_length=2, max_length=64)
    color: str = Field(min_length=2, max_length=64)
    material: str = Field(min_length=2, max_length=64)
    occasion: str = Field(min_length=2, max_length=64)
    style: str = Field(min_length=2, max_length=64)
    gender: str = Field(pattern=r"^(women|men|unisex|kids)$")
    sizes: list[str] = Field(min_length=1)
    price_inr: int = Field(ge=100, le=100_000)
    description: str = Field(min_length=20, max_length=2000)
    image_reference: str = Field(min_length=1, max_length=512)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=255)

    @field_validator("sizes")
    @classmethod
    def sizes_must_be_unique(cls, value: list[str]) -> list[str]:
        """Reject empty or duplicate size labels while preserving their order."""
        normalized = [size.strip() for size in value]
        if any(not size for size in normalized):
            raise ValueError("sizes cannot contain empty labels")
        if len(normalized) != len(set(normalized)):
            raise ValueError("sizes must be unique")
        return normalized


class ProductRecord(ProductCreate):
    """Public product card returned to the shopper."""

    id: int
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @computed_field
    @property
    def product_url(self) -> str:
        """Return the stable relative application URL for this catalog item."""
        return f"/products/{self.slug}"


class ProductFilters(BaseModel):
    """Structured filters parsed from a natural-language shopping query."""

    color: str | None = None
    category: str | None = None
    occasion: str | None = None
    max_price_inr: int | None = Field(default=None, ge=0)
    query_text: str | None = None
