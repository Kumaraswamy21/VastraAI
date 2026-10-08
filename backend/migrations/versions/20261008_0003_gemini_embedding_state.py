"""Widen product embeddings for Gemini and add generation state columns."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261008_0003"
down_revision: str | None = "20261008_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE products ALTER COLUMN embedding TYPE vector(768) USING NULL")
    op.add_column("products", sa.Column("embedding_provider", sa.String(length=32), nullable=True))
    op.add_column("products", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("embedding_text_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "products",
        sa.Column("embedding_status", sa.String(length=16), nullable=False, server_default="PENDING"),
    )
    op.add_column(
        "products",
        sa.Column("embedding_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("products", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_products_embedding_status",
        "products",
        "embedding_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
    )
    op.create_index("ix_products_embedding_status", "products", ["embedding_status"])
    op.create_index("ix_products_embedding_text_hash", "products", ["embedding_text_hash"])


def downgrade() -> None:
    op.drop_index("ix_products_embedding_text_hash", table_name="products")
    op.drop_index("ix_products_embedding_status", table_name="products")
    op.drop_constraint("ck_products_embedding_status", "products", type_="check")
    op.drop_column("products", "embedding_error")
    op.drop_column("products", "embedding_generated_at")
    op.drop_column("products", "embedding_status")
    op.drop_column("products", "embedding_text_hash")
    op.drop_column("products", "embedding_dimensions")
    op.drop_column("products", "embedding_model")
    op.drop_column("products", "embedding_provider")
    op.execute("ALTER TABLE products ALTER COLUMN embedding TYPE vector(384) USING NULL")
