"""Idempotently insert the deterministic synthetic catalog."""

import argparse

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from fashion_search.catalog.generator import DEFAULT_PRODUCT_COUNT, DEFAULT_SEED, generate_catalog
from fashion_search.catalog.models import Product
from fashion_search.core.db import get_engine


def seed_catalog(count: int, seed: int) -> tuple[int, int, int]:
    """Validate, insert missing slugs, and return generated/inserted/total counts."""
    products = generate_catalog(count=count, seed=seed)
    rows = [product.model_dump() for product in products]
    statement = insert(Product).values(rows).on_conflict_do_nothing(index_elements=[Product.slug])
    with get_engine().begin() as connection:
        before = connection.scalar(select(func.count()).select_from(Product)) or 0
        connection.execute(statement)
        total = connection.scalar(select(func.count()).select_from(Product)) or 0
        inserted = total - before
    return len(products), inserted, total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=DEFAULT_PRODUCT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated, inserted, total = seed_catalog(args.count, args.seed)
    print(f"generated={generated} inserted={inserted} total={total} seed={args.seed}")


if __name__ == "__main__":
    main()
