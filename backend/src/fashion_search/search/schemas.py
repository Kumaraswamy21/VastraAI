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
    extraction_method: Literal["gemini", "ollama", "fallback"]


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
    embedding_provider: str = "gemini"
    embedding_index_status: Literal["ready", "empty", "incompatible", "unknown"] = "unknown"
    results: list[SemanticSearchHit]


class HybridSearchRequest(BaseModel):
    """Natural-language hybrid search request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value.strip()


class HybridSearchScores(BaseModel):
    """Ranking diagnostics for one hybrid result (RRF is not a probability)."""

    semantic_similarity: float | None = None
    keyword_rank_score: float | None = None
    semantic_rank: int | None = Field(default=None, ge=1)
    keyword_rank: int | None = Field(default=None, ge=1)
    hybrid_score: float = Field(ge=0)


class RankingEvidence(BaseModel):
    """Observable signals behind a result; scores are not probabilities."""

    semantic_similarity: float | None = Field(default=None, ge=-1.0, le=1.0)
    semantic_rank: int | None = Field(default=None, ge=1)
    keyword_score: float | None = Field(default=None, ge=0)
    keyword_rank: int | None = Field(default=None, ge=1)
    hybrid_score: float = Field(ge=0)
    final_rank: int = Field(ge=1)
    ranking_sources: list[Literal["semantic", "keyword"]]
    matched_constraints: list[
        Literal["category", "color", "occasion", "size", "gender", "price"]
    ]


class SearchDiagnostics(BaseModel):
    """Progressive hard-filter counts collected in one aggregate query."""

    enabled: bool = True
    initial_catalog: int = Field(ge=0)
    exact_match_count: int = Field(ge=0)
    filter_counts: dict[str, int] = Field(default_factory=dict)
    eliminated_by: str | None = None


class HybridSearchResult(BaseModel):
    """One fused product hit."""

    product_id: int
    title: str
    category: str
    color: str
    material: str
    style: str
    gender: str
    occasion: str
    sizes: list[str] = Field(default_factory=list)
    price_inr: int
    currency: str = "INR"
    image_reference: str
    product_url: str
    scores: HybridSearchScores
    match_quality: Literal["strong", "good", "weak"]
    match_reason: str
    ranking: RankingEvidence


class HybridSearchResponse(BaseModel):
    """Hybrid search payload; total is the number of returned rows."""

    query: str
    retrieval_query: str
    filters: dict[str, object]
    total: int = Field(ge=0)
    results: list[HybridSearchResult]
    search_status: Literal[
        "success",
        "no_exact_matches",
        "no_relevant_matches",
        "no_results",
        "unsupported_constraints",
    ] = "success"
    message: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    diagnostics: SearchDiagnostics | None = None
    search_mode: Literal["hybrid", "keyword_fallback", "semantic_fallback"] = "hybrid"
    semantic_search_available: bool = True
    embedding_index_status: Literal["ready", "empty", "incompatible", "unknown"] = "unknown"
    metrics: dict[str, object] = Field(default_factory=dict)
