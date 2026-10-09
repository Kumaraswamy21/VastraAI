"""Development-only, bounded observability analytics API."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from fashion_search.config.settings import Settings, get_settings
from fashion_search.observability.repository import repository

router = APIRouter(prefix="/dev/observability", tags=["developer-observability"])
Range = Literal["1h", "24h", "7d"]


def require_dashboard(settings: Settings = Depends(get_settings)) -> None:
    if (
        not settings.observability_enabled
        or not settings.observability_dashboard_enabled
        or settings.app_environment == "production"
    ):
        raise HTTPException(status_code=404, detail="Not found")


def since_for(value: Range) -> datetime:
    delta = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }[value]
    return datetime.now(timezone.utc) - delta


@router.get("/summary", dependencies=[Depends(require_dashboard)])
def summary(range: Range = "24h"):
    return {"range": range, **repository.summary(since_for(range))}


@router.get("/providers", dependencies=[Depends(require_dashboard)])
def providers(
    range: Range = "24h",
    provider: str | None = Query(default=None, max_length=32),
    model: str | None = Query(default=None, max_length=160),
    operation: str | None = Query(default=None, max_length=40),
    outcome: str | None = Query(default=None, max_length=32),
):
    filters = {
        "provider": provider,
        "model": model,
        "operation": operation,
        "outcome": outcome,
    }
    since = since_for(range)
    return {
        "range": range,
        "breakdown": repository.providers(since, filters),
        "recent": repository.recent_providers(since, filters),
    }


@router.get("/search", dependencies=[Depends(require_dashboard)])
def searches(
    range: Range = "24h", search_mode: str | None = Query(default=None, max_length=32)
):
    return {"range": range, **repository.searches(since_for(range), search_mode)}


@router.get("/requests/{request_id}", dependencies=[Depends(require_dashboard)])
def request_detail(request_id: str):
    if len(request_id) > 36:
        raise HTTPException(status_code=422, detail="invalid request ID")
    detail = repository.request_detail(request_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="request not found")
    return detail
