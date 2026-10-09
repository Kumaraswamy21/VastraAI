"""allow provider-specific embedding dimensions

Revision ID: 20261009_0005
Revises: 20261008_0004
"""

from alembic import op

revision = "20261009_0005"
down_revision = "20261008_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE products ALTER COLUMN embedding "
        "TYPE vector USING embedding::vector"
    )


def downgrade() -> None:
    # Vectors with other dimensions cannot be cast to vector(768). Preserve
    # catalog rows but clear incompatible vectors before restoring the old type.
    op.execute(
        "UPDATE products SET embedding = NULL, embedding_status = 'PENDING', "
        "embedding_provider = NULL, embedding_model = NULL, "
        "embedding_dimensions = NULL WHERE embedding_dimensions <> 768"
    )
    op.execute(
        "ALTER TABLE products ALTER COLUMN embedding "
        "TYPE vector(768) USING embedding::vector(768)"
    )
