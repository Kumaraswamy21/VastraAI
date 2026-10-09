"""add provider and search observability events

Revision ID: 20261009_0006
Revises: 20261009_0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261009_0006"
down_revision = "20261009_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("search_request_id", sa.String(36)),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Numeric(18, 10)),
        sa.Column("cost_currency", sa.String(3)),
        sa.Column("pricing_effective_date", sa.String(10)),
        sa.Column("error_type", sa.String(80)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_ai_events_timestamp", "ai_provider_events", ["timestamp"])
    op.create_index("ix_ai_events_provider_model", "ai_provider_events", ["provider", "model"])
    op.create_index("ix_ai_events_operation_outcome", "ai_provider_events", ["operation", "outcome"])
    op.create_index("ix_ai_events_search_request", "ai_provider_events", ["search_request_id"])

    op.create_table(
        "search_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36)),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("search_mode", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("total_latency_ms", sa.Float(), nullable=False),
        sa.Column("constraint_parsing_ms", sa.Float()),
        sa.Column("query_embedding_ms", sa.Float()),
        sa.Column("semantic_search_ms", sa.Float()),
        sa.Column("keyword_search_ms", sa.Float()),
        sa.Column("fusion_ms", sa.Float()),
        sa.Column("explanation_ms", sa.Float()),
        sa.Column("semantic_candidate_count", sa.Integer()),
        sa.Column("keyword_candidate_count", sa.Integer()),
        sa.Column("final_result_count", sa.Integer()),
        sa.Column("generation_provider", sa.String(32)),
        sa.Column("embedding_provider", sa.String(32)),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("semantic_search_available", sa.Boolean(), nullable=False),
        sa.Column("error_type", sa.String(80)),
        sa.Column("query_hash", sa.String(64)),
        sa.Column("redacted_query", sa.Text()),
        sa.UniqueConstraint("request_id", name="uq_search_events_request_id"),
    )
    op.create_index("ix_search_events_timestamp", "search_events", ["timestamp"])
    op.create_index("ix_search_events_mode_outcome", "search_events", ["search_mode", "outcome"])
    op.create_index("ix_search_events_session", "search_events", ["session_id"])


def downgrade() -> None:
    op.drop_table("search_events")
    op.drop_table("ai_provider_events")
