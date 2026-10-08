"""Print deterministic catalog distribution checks from PostgreSQL."""

from sqlalchemy import case, func, select

from fashion_search.catalog.models import Product
from fashion_search.core.db import get_engine


def print_group_counts(label: str, column: object) -> None:
    """Print ordered counts for a single catalog dimension."""
    statement = select(column, func.count()).select_from(Product).group_by(column).order_by(column)
    print(f"\n{label}")
    with get_engine().connect() as connection:
        for value, count in connection.execute(statement):
            print(f"  {value}: {count}")


def print_price_ranges() -> None:
    """Print counts in useful INR shopping bands."""
    price_range = case(
        (Product.price_inr < 1000, "under_1000"),
        (Product.price_inr < 2500, "1000_2499"),
        (Product.price_inr < 5000, "2500_4999"),
        (Product.price_inr < 10000, "5000_9999"),
        else_="10000_plus",
    )
    statement = (
        select(price_range.label("price_range"), func.count())
        .select_from(Product)
        .group_by(price_range)
        .order_by(price_range)
    )
    print("\nprice_range_inr")
    with get_engine().connect() as connection:
        for value, count in connection.execute(statement):
            print(f"  {value}: {count}")


def main() -> None:
    with get_engine().connect() as connection:
        total = connection.scalar(select(func.count()).select_from(Product)) or 0
        null_embeddings = connection.scalar(
            select(func.count()).select_from(Product).where(Product.embedding.is_(None))
        ) or 0
        null_search_vectors = connection.scalar(
            select(func.count()).select_from(Product).where(Product.search_vector.is_(None))
        ) or 0
    print(f"total: {total}")
    print(f"null_embeddings: {null_embeddings}")
    print(f"null_search_vectors: {null_search_vectors}")
    print_group_counts("category", Product.category)
    print_group_counts("color", Product.color)
    print_price_ranges()


if __name__ == "__main__":
    main()
