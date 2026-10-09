"""Small helpers for connecting to PostgreSQL."""

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from fashion_search.config.settings import get_settings


def sqlalchemy_url(database_url: str) -> str:
    """Use the psycopg driver when the URL is a plain postgresql:// string."""
    prefix = "postgresql://"
    if database_url.startswith(prefix):
        return "postgresql+psycopg://" + database_url.removeprefix(prefix)
    return database_url


def ensure_sslmode(database_url: str) -> str:
    """Require SSL when the connection string does not already set sslmode."""
    if "sslmode=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}sslmode=require"


def engine_from_url(url: str) -> Engine:
    """Build a SQLAlchemy engine from the configured PostgreSQL URL."""
    return create_engine(
        ensure_sslmode(sqlalchemy_url(url)),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


@lru_cache
def get_engine() -> Engine:
    """Return a process-wide cached engine from settings."""
    return engine_from_url(get_settings().database_url)


def ping_database(engine: Engine) -> None:
    """Run SELECT 1 to confirm connectivity."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
