"""SQLAlchemy catalog tables."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for catalog tables."""


class Product(Base):
    """A sellable fashion item in the synthetic catalog."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(64), nullable=False)
    material: Mapped[str] = mapped_column(String(64), nullable=False)
    occasion: Mapped[str] = mapped_column(String(64), nullable=False)
    style: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    sizes: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False)
    price_inr: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        CheckConstraint("price_inr >= 100", name="ck_products_price_inr_positive"),
        CheckConstraint(
            "gender IN ('women', 'men', 'unisex', 'kids')",
            name="ck_products_gender_allowed",
        ),
        CheckConstraint("cardinality(sizes) > 0", name="ck_products_sizes_nonempty"),
    )
