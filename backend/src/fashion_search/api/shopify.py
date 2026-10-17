"""Live product discovery through Shopify Global Catalog MCP."""

from fastapi import APIRouter, Depends, HTTPException

from fashion_search.config.settings import get_settings
from fashion_search.shopify.client import ShopifyMcpError, search_global_catalog
from fashion_search.shopify.schemas import ShopifySearchRequest, ShopifySearchResponse
from fashion_search.auth.security import current_user
from fashion_search.catalog.models import User

router = APIRouter(prefix="/search/shopify", tags=["shopify"])


@router.post("", response_model=ShopifySearchResponse)
def search_shopify(
    body: ShopifySearchRequest, _user: User = Depends(current_user)
) -> ShopifySearchResponse:
    """Search live Shopify offers without storing or mixing them into local RAG."""
    settings = get_settings()
    try:
        result = search_global_catalog(
            body.query,
            limit=body.limit,
            settings=settings,
        )
    except ShopifyMcpError as exc:
        status_code = (
            503
            if not settings.shopify_catalog_enabled
            or not settings.shopify_agent_profile_url
            or bool(settings.shopify_client_id) != bool(settings.shopify_client_secret)
            else 502
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ShopifySearchResponse(query=body.query, **result)
