"""Create the synthetic fashion products catalog."""

from typing import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261007_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=64), nullable=False),
        sa.Column("material", sa.String(length=64), nullable=False),
        sa.Column("occasion", sa.String(length=64), nullable=False),
        sa.Column("style", sa.String(length=64), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=False),
        sa.Column("sizes", postgresql.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("price_inr", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_reference", sa.String(length=512), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("embedding", Vector(dim=384), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.CheckConstraint(
            "gender IN ('women', 'men', 'unisex', 'kids')",
            name="ck_products_gender_allowed",
        ),
        sa.CheckConstraint("price_inr >= 100", name="ck_products_price_inr_positive"),
        sa.CheckConstraint("cardinality(sizes) > 0", name="ck_products_sizes_nonempty"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_products_slug", table_name="products")
    op.drop_table("products")
