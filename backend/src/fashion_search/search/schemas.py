"""Request and response shapes for semantic product search."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
