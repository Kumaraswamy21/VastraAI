"""Liveness endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a static liveness payload."""
    return {"status": "ok", "service": "fashion-search"}
