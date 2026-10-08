"""Validated query parameters for catalog browsing."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

SortOption = Literal["newest", "price_asc", "price_desc"]


class ProductListQuery(BaseModel):
    """Exact filters, price range, sort, and pagination for GET /products."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=24, ge=1, le=48)
    category: str | None = Field(default=None, min_length=1)
    color: str | None = Field(default=None, min_length=1)
    gender: str | None = Field(default=None, min_length=1)
    occasion: str | None = Field(default=None, min_length=1)
    style: str | None = Field(default=None, min_length=1)
    size: str | None = Field(default=None, min_length=1)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    sort: SortOption = "newest"

    @model_validator(mode="after")
    def min_price_not_above_max(self) -> "ProductListQuery":
        """Reject inverted price ranges with a 422-friendly validation error."""
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")
        return self
