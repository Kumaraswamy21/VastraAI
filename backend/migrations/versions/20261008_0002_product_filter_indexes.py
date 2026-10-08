"""Add btree and GIN indexes for catalog filter columns."""

from typing import Sequence

from alembic import op


revision: str = "20261008_0002"
down_revision: str | None = "20261007_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_color", "products", ["color"])
    op.create_index("ix_products_gender", "products", ["gender"])
    op.create_index("ix_products_occasion", "products", ["occasion"])
    op.create_index("ix_products_style", "products", ["style"])
    op.create_index("ix_products_price_inr", "products", ["price_inr"])
    op.create_index(
        "ix_products_sizes",
        "products",
        ["sizes"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_products_sizes", table_name="products")
    op.drop_index("ix_products_price_inr", table_name="products")
    op.drop_index("ix_products_style", table_name="products")
    op.drop_index("ix_products_occasion", table_name="products")
    op.drop_index("ix_products_gender", table_name="products")
    op.drop_index("ix_products_color", table_name="products")
    op.drop_index("ix_products_category", table_name="products")
