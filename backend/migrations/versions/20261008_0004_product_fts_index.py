"""Maintain weighted product search_vector and GIN index for FTS."""

from typing import Sequence

from alembic import op

revision: str = "20261008_0004"
down_revision: str | None = "20261008_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEARCH_VECTOR_EXPR = """
setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
setweight(to_tsvector('english', coalesce(category, '')), 'B') ||
setweight(
    to_tsvector(
        'english',
        trim(
            coalesce(color, '') || ' ' ||
            coalesce(material, '') || ' ' ||
            coalesce(style, '')
        )
    ),
    'C'
) ||
setweight(to_tsvector('english', coalesce(description, '')), 'D')
"""


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION products_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := """
        + _SEARCH_VECTOR_EXPR
        + """;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS products_search_vector_trigger ON products")
    op.execute(
        """
        CREATE TRIGGER products_search_vector_trigger
        BEFORE INSERT OR UPDATE OF title, category, color, material, style, description
        ON products
        FOR EACH ROW
        EXECUTE FUNCTION products_search_vector_update();
        """
    )
    op.execute(
        f"""
        UPDATE products
        SET search_vector = {_SEARCH_VECTOR_EXPR};
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS products_search_vector_gin_idx
        ON products
        USING GIN (search_vector);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS products_search_vector_gin_idx")
    op.execute("DROP TRIGGER IF EXISTS products_search_vector_trigger ON products")
    op.execute("DROP FUNCTION IF EXISTS products_search_vector_update()")
