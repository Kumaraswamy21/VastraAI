"""Provider-neutral telemetry value objects and API schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderOperation = Literal[
    "generation", "structured_generation", "query_embedding", "document_embedding"
]
ProviderOutcome = Literal[
    "SUCCESS", "FAILED", "TIMEOUT", "RATE_LIMITED", "UNAVAILABLE", "INVALID_RESPONSE"
]


class AIUsage(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AIProviderEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    search_request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str
    model: str
    operation: ProviderOperation
    outcome: ProviderOutcome
    latency_ms: float = Field(ge=0)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: Decimal | None = None
    cost_currency: str | None = None
    pricing_effective_date: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    fallback_used: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    search_mode: str
    outcome: str
    total_latency_ms: float = Field(ge=0)
    constraint_parsing_ms: float | None = None
    query_embedding_ms: float | None = None
    semantic_search_ms: float | None = None
    keyword_search_ms: float | None = None
    fusion_ms: float | None = None
    explanation_ms: float | None = None
    semantic_candidate_count: int | None = None
    keyword_candidate_count: int | None = None
    final_result_count: int | None = None
    generation_provider: str | None = None
    embedding_provider: str | None = None
    fallback_used: bool = False
    semantic_search_available: bool = True
    error_type: str | None = None
    query_hash: str | None = None
    redacted_query: str | None = None


class ModelPricing(BaseModel):
    provider: str
    model: str
    input_cost_per_million_tokens: Decimal | None = None
    output_cost_per_million_tokens: Decimal | None = None
    embedding_cost_per_million_tokens: Decimal | None = None
    currency: str = "USD"
    effective_date: str
