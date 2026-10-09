"""Liveness and PostgreSQL connectivity endpoint."""

from fastapi import APIRouter

from fashion_search.core.db import get_engine, ping_database
from fashion_search.core.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


def database_status() -> str:
    """Ping PostgreSQL; return ok or error without raising to the client."""
    try:
        ping_database(get_engine())
        return "ok"
    except Exception:
        logger.exception("Database health check failed")
        return "error"


def overall_status(database: str) -> str:
    """Combine backend (always up if we respond) with database ping."""
    return "ok" if database == "ok" else "degraded"


@router.get("/health")
def health() -> dict[str, str]:
    """Return backend liveness and PostgreSQL connectivity."""
    database = database_status()
    return {
        "status": overall_status(database),
        "backend": "ok",
        "database": database,
    }
