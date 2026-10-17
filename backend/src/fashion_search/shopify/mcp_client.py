"""Isolated client for Shopify Global Catalog MCP."""

from __future__ import annotations

import json
from typing import Any

import httpx

from fashion_search.config.settings import Settings


class ShopifyMcpError(Exception):
    """Base error for Shopify MCP requests."""


class ShopifyMcpTimeoutError(ShopifyMcpError):
    """The MCP server did not respond before the configured timeout."""


class ShopifyMcpRateLimitError(ShopifyMcpError):
    """The MCP server rejected a request due to rate limiting."""

    def __init__(self, message: str, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ShopifyMcpProtocolError(ShopifyMcpError):
    """The MCP server returned a JSON-RPC or tool error."""


class ShopifyMcpClient:
    """Call Shopify's documented JSON-RPC MCP endpoint without storing results."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=settings.shopify_mcp_timeout_seconds
        )
        self._request_id = 0
        self._closed = False

    def __enter__(self) -> ShopifyMcpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client only when this instance created it."""
        if not self._closed:
            if self._owns_client:
                self._client.close()
            self._closed = True

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tools advertised by the endpoint's tools/list method."""
        envelope = self._request("tools/list")
        result = envelope.get("result")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list) or not all(isinstance(x, dict) for x in tools):
            raise ShopifyMcpProtocolError("Shopify MCP returned an invalid tools list")
        return tools

    def search_catalog(
        self,
        query: str,
        *,
        limit: int = 10,
        country: str | None = None,
        currency: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search the catalog and return Shopify's raw structured tool content."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        profile = self.settings.shopify_agent_profile_url
        if not profile:
            raise ShopifyMcpError("Shopify UCP agent profile URL is not configured")

        destination = (country or self.settings.shopify_catalog_country).upper()
        context = {"address_country": destination}
        if currency:
            context["currency"] = currency.upper()
        catalog: dict[str, Any] = {
            "query": query,
            "pagination": {"limit": limit},
            "context": context,
        }
        if filters is not None:
            catalog["filters"] = filters
        arguments = {
            "meta": {"ucp-agent": {"profile": profile}},
            "catalog": catalog,
        }
        envelope = self._request(
            "tools/call",
            params={"name": "search_catalog", "arguments": arguments},
        )
        result = envelope.get("result")
        if not isinstance(result, dict) or result.get("isError"):
            raise ShopifyMcpProtocolError("Shopify search_catalog tool failed")
        content = result.get("structuredContent")
        if isinstance(content, dict):
            return content
        blocks = result.get("content", [])
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                try:
                    parsed = json.loads(block["text"])
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
        raise ShopifyMcpProtocolError("Shopify MCP omitted structured search results")

    def _request(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise ShopifyMcpError("Shopify MCP client is closed")
        self._request_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._request_id,
        }
        if params is not None:
            payload["params"] = params

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        client_id = self.settings.shopify_client_id
        client_secret = self.settings.shopify_client_secret
        if bool(client_id) != bool(client_secret):
            raise ShopifyMcpError("Both Shopify client ID and secret are required")
        try:
            if client_id and client_secret:
                token_response = self._client.post(
                    self.settings.shopify_token_url,
                    json={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "grant_type": "client_credentials",
                    },
                    headers={"Content-Type": "application/json"},
                )
                self._check_status(token_response, stage="token endpoint")
                token = token_response.json().get("access_token")
                if not isinstance(token, str) or not token:
                    raise ShopifyMcpProtocolError(
                        "Shopify authentication returned no access token"
                    )
                headers["Authorization"] = f"Bearer {token}"
            response = self._client.post(
                self.settings.shopify_mcp_url, json=payload, headers=headers
            )
            self._check_status(response, stage="catalog endpoint")
            try:
                envelope = response.json()
            except (ValueError, json.JSONDecodeError) as exc:
                raise ShopifyMcpProtocolError(
                    "Shopify MCP returned invalid JSON"
                ) from exc
        except httpx.TimeoutException as exc:
            raise ShopifyMcpTimeoutError("Shopify MCP request timed out") from exc
        except httpx.HTTPError as exc:
            raise ShopifyMcpError("Shopify MCP request failed") from exc

        if not isinstance(envelope, dict):
            raise ShopifyMcpProtocolError("Shopify MCP returned an invalid response")
        if envelope.get("error"):
            raise ShopifyMcpProtocolError("Shopify MCP returned a JSON-RPC error")
        return envelope

    @staticmethod
    def _check_status(response: httpx.Response, *, stage: str) -> None:
        if response.status_code == 429:
            raise ShopifyMcpRateLimitError(
                "Shopify MCP rate limit reached",
                retry_after=response.headers.get("Retry-After"),
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ShopifyMcpError(
                f"Shopify {stage} returned HTTP {response.status_code}"
            ) from exc
