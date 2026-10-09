"""PostgreSQL telemetry tables."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fashion_search.catalog.models import Base


class AIProviderEvent(Base):
    __tablename__ = "ai_provider_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    search_request_id: Mapped[str | None] = mapped_column(String(36))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    cost_currency: Mapped[str | None] = mapped_column(String(3))
    pricing_effective_date: Mapped[str | None] = mapped_column(String(10))
    error_type: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(80))
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )


class SearchEvent(Base):
    __tablename__ = "search_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    session_id: Mapped[str | None] = mapped_column(String(36))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    search_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    constraint_parsing_ms: Mapped[float | None] = mapped_column(Float)
    query_embedding_ms: Mapped[float | None] = mapped_column(Float)
    semantic_search_ms: Mapped[float | None] = mapped_column(Float)
    keyword_search_ms: Mapped[float | None] = mapped_column(Float)
    fusion_ms: Mapped[float | None] = mapped_column(Float)
    explanation_ms: Mapped[float | None] = mapped_column(Float)
    semantic_candidate_count: Mapped[int | None] = mapped_column(Integer)
    keyword_candidate_count: Mapped[int | None] = mapped_column(Integer)
    final_result_count: Mapped[int | None] = mapped_column(Integer)
    generation_provider: Mapped[str | None] = mapped_column(String(32))
    embedding_provider: Mapped[str | None] = mapped_column(String(32))
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    semantic_search_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(80))
    query_hash: Mapped[str | None] = mapped_column(String(64))
    redacted_query: Mapped[str | None] = mapped_column(Text)
