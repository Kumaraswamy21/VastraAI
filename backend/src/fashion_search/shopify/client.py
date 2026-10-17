"""Small HTTPX client for Shopify's Global Catalog MCP tool."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import httpx

from fashion_search.config.settings import Settings
from fashion_search.shopify.schemas import map_shopify_product


class ShopifyMcpError(Exception):
    """A disabled, unavailable, or invalid Shopify MCP request."""


_TOKEN_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
_TOKEN_CACHE_LOCK = threading.Lock()


def _get_access_token(
    transport: httpx.Client,
    *,
    settings: Settings,
) -> str | None:
    """Return an optional token, reusing it when credentials are configured."""
    if bool(settings.shopify_client_id) != bool(settings.shopify_client_secret):
        raise ShopifyMcpError("Both Shopify client ID and secret are required")
    if not settings.shopify_client_id:
        return None
    key = (settings.shopify_client_id, settings.shopify_client_secret)
    now = time.monotonic()
    with _TOKEN_CACHE_LOCK:
        cached = _TOKEN_CACHE.get(key)
        if cached and cached[1] > now:
            return cached[0]
        response = transport.post(
            settings.shopify_token_url,
            json={
                "client_id": settings.shopify_client_id,
                "client_secret": settings.shopify_client_secret,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        body = response.json()
        token = body.get("access_token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise ShopifyMcpError("Shopify authentication returned no access token")
        # Shopify documents a 60-minute token lifetime; refresh five minutes early.
        _TOKEN_CACHE[key] = (token, now + 55 * 60)
        return token


def _response_json(response: httpx.Response) -> dict[str, Any]:
    body = response.text.strip()
    if body.startswith("event:") or "\ndata:" in body:
        data = [
            line[5:].strip() for line in body.splitlines() if line.startswith("data:")
        ]
        body = data[-1] if data else ""
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ShopifyMcpError("Shopify MCP returned an unreadable response") from exc
    if not isinstance(parsed, dict):
        raise ShopifyMcpError("Shopify MCP returned an invalid response")
    return parsed


def search_global_catalog(
    query: str,
    *,
    limit: int,
    settings: Settings,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Call search_catalog and return only live, validated product fields."""
    if not settings.shopify_catalog_enabled:
        raise ShopifyMcpError("Shopify catalog search is not enabled")
    if not settings.shopify_agent_profile_url:
        raise ShopifyMcpError("Shopify agent profile URL is not configured")

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {
            "name": "search_catalog",
            "arguments": {
                "meta": {"ucp-agent": {"profile": settings.shopify_agent_profile_url}},
                "catalog": {
                    "query": query,
                    "filters": {
                        "available": True,
                        "ships_to": {
                            "country": settings.shopify_catalog_country.upper()
                        },
                    },
                    "context": {
                        "address_country": settings.shopify_catalog_country.upper()
                    },
                    "pagination": {"limit": limit},
                },
            },
        },
    }
    owns_client = client is None
    transport = client or httpx.Client(timeout=settings.shopify_mcp_timeout_seconds)
    try:
        access_token = _get_access_token(transport, settings=settings)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        response = transport.post(
            settings.shopify_mcp_url,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        envelope = _response_json(response)
    except (httpx.HTTPError, ShopifyMcpError) as exc:
        raise ShopifyMcpError(
            "Shopify catalog search is temporarily unavailable"
        ) from exc
    finally:
        if owns_client:
            transport.close()

    result_envelope = envelope.get("result")
    if envelope.get("error"):
        raise ShopifyMcpError("Shopify catalog search returned an error")
    if not isinstance(result_envelope, dict) or result_envelope.get("isError"):
        raise ShopifyMcpError("Shopify catalog search returned an error")
    result = result_envelope
    content = result.get("structuredContent")
    if not isinstance(content, dict):
        text_blocks = result.get("content") or []
        text_block = next(
            (
                item.get("text")
                for item in text_blocks
                if isinstance(item, dict) and item.get("text")
            ),
            None,
        )
        if isinstance(text_block, str):
            try:
                content = json.loads(text_block)
            except json.JSONDecodeError as exc:
                raise ShopifyMcpError(
                    "Shopify MCP returned an invalid tool result"
                ) from exc
    if not isinstance(content, dict):
        raise ShopifyMcpError("Shopify MCP omitted structured catalog results")

    raw_products = content.get("products") or []
    products = [
        mapped
        for raw in raw_products
        if isinstance(raw, dict)
        if (mapped := map_shopify_product(raw)) is not None
    ]
    pagination = content.get("pagination") or {}
    return {
        "results": products,
        "total": len(products),
        "has_next_page": bool(pagination.get("has_next_page", False)),
    }
