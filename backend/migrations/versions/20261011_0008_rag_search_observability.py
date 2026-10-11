"""Add bounded RAG timing, context, provider, and grounding measurements."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261011_0008"
down_revision: str | None = "20261009_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, column in (
        ("retrieval_latency_ms", sa.Float()),
        ("rag_generation_latency_ms", sa.Float()),
        ("total_rag_latency_ms", sa.Float()),
        ("retrieved_context_count", sa.Integer()),
        ("context_size_chars", sa.Integer()),
        ("generation_model", sa.String(160)),
    ):
        op.add_column("search_events", sa.Column(name, column, nullable=True))
    op.add_column(
        "search_events",
        sa.Column(
            "grounding_failure", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "search_events",
        sa.Column(
            "invalid_product_reference",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    for name in (
        "invalid_product_reference",
        "grounding_failure",
        "generation_model",
        "context_size_chars",
        "retrieved_context_count",
        "total_rag_latency_ms",
        "rag_generation_latency_ms",
        "retrieval_latency_ms",
    ):
        op.drop_column("search_events", name)
