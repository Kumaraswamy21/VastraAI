"""Qualify product columns in the FTS row trigger for existing databases."""

from typing import Sequence

from alembic import op

revision: str = "20261009_0007"
down_revision: str | None = "20261009_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION products_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.category, '')), 'B') ||
                setweight(to_tsvector('english', trim(
                    coalesce(NEW.color, '') || ' ' ||
                    coalesce(NEW.material, '') || ' ' ||
                    coalesce(NEW.style, '')
                )), 'C') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # The previous trigger was broken for writes; retain the corrected definition.
    pass
