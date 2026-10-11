"""Focused protocol tests for the isolated Shopify MCP client."""

from __future__ import annotations

import unittest
from typing import Any

import httpx

from fashion_search.config.settings import Settings
from fashion_search.shopify.mcp_client import (
    ShopifyMcpClient,
    ShopifyMcpError,
    ShopifyMcpProtocolError,
    ShopifyMcpRateLimitError,
    ShopifyMcpTimeoutError,
)


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "postgresql://unused",
        "shopify_agent_profile_url": "https://example.test/ucp-profile.json",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class ShopifyMcpClientTests(unittest.TestCase):
    def test_lists_tools_using_json_rpc(self) -> None:
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "tools": [
                            {"name": "search_catalog"},
                            {"name": "get_product"},
                            {"name": "lookup_catalog"},
                        ]
                    },
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with ShopifyMcpClient(settings(), client=client) as mcp:
            tools = mcp.list_tools()
        self.assertEqual(
            [tool["name"] for tool in tools],
            ["search_catalog", "get_product", "lookup_catalog"],
        )
        self.assertEqual(captured[0].url.path, "/api/ucp/mcp")
        self.assertEqual(captured[0].headers["accept"], "application/json, text/event-stream")
        self.assertEqual(captured[0].read(), b'{"jsonrpc":"2.0","method":"tools/list","id":1}')
        self.assertFalse(client.is_closed, "injected HTTP clients remain caller-owned")
        client.close()

    def test_search_returns_raw_structured_content_and_sends_profile(self) -> None:
        captured: list[httpx.Request] = []
        response_body = {
            "ucp": {"version": "2026-01-11"},
            "products": [{"title": "Blue cotton kurta", "price": {"amount": 120000}}],
            "messages": [],
            "pagination": {"has_next_page": True, "total_count": 459},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": response_body}},
            )

        transport = httpx.Client(transport=httpx.MockTransport(handler))
        with ShopifyMcpClient(settings(), client=transport) as mcp:
            result = mcp.search_catalog(
                "blue cotton kurta under INR 1500",
                limit=5,
                filters={"available": True},
            )
        self.assertEqual(result, response_body)
        request = captured[0]
        self.assertNotIn("authorization", request.headers)
        body = __import__("json").loads(request.read())
        self.assertEqual(body["method"], "tools/call")
        self.assertEqual(body["params"]["name"], "search_catalog")
        args = body["params"]["arguments"]
        self.assertEqual(
            args["meta"]["ucp-agent"]["profile"],
            "https://example.test/ucp-profile.json",
        )
        self.assertEqual(args["catalog"]["query"], "blue cotton kurta under INR 1500")
        self.assertEqual(args["catalog"]["pagination"], {"limit": 5})
        self.assertEqual(args["catalog"]["filters"], {"available": True})
        transport.close()

    def test_uses_client_credentials_when_configured(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.host == "auth.test":
                return httpx.Response(200, json={"access_token": "short-lived-token"})
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}},
            )

        cfg = settings(
            shopify_token_url="https://auth.test/access_token",
            shopify_client_id="client-id",
            shopify_client_secret="client-secret",
        )
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with ShopifyMcpClient(cfg, client=client) as mcp:
            mcp.list_tools()
        self.assertEqual(requests[0].read(), b'{"client_id":"client-id","client_secret":"client-secret","grant_type":"client_credentials"}')
        self.assertEqual(requests[1].headers["authorization"], "Bearer short-lived-token")
        client.close()

    def test_timeout_is_reported(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("late")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with ShopifyMcpClient(settings(), client=client) as mcp:
            with self.assertRaises(ShopifyMcpTimeoutError):
                mcp.list_tools()
        client.close()

    def test_rate_limit_includes_retry_after(self) -> None:
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with ShopifyMcpClient(settings(), client=client) as mcp:
            with self.assertRaises(ShopifyMcpRateLimitError) as caught:
                mcp.list_tools()
        self.assertEqual(caught.exception.retry_after, "2")
        client.close()

    def test_json_rpc_and_tool_errors_are_reported(self) -> None:
        for envelope in (
            {"jsonrpc": "2.0", "id": 1, "error": {"message": "invalid"}},
            {"jsonrpc": "2.0", "id": 1, "result": {"isError": True}},
        ):
            client = httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json=envelope)
                )
            )
            with ShopifyMcpClient(settings(), client=client) as mcp:
                if "error" in envelope:
                    with self.assertRaises(ShopifyMcpProtocolError):
                        mcp.list_tools()
                else:
                    with self.assertRaises(ShopifyMcpProtocolError):
                        mcp.search_catalog("kurta")
            client.close()

    def test_missing_profile_and_incomplete_credentials_fail_before_request(self) -> None:
        client = httpx.Client(transport=httpx.MockTransport(lambda _: self.fail("sent")))
        with ShopifyMcpClient(settings(shopify_agent_profile_url=""), client=client) as mcp:
            with self.assertRaises(ShopifyMcpError):
                mcp.search_catalog("kurta")
        with ShopifyMcpClient(
            settings(shopify_client_id="only-id"), client=client
        ) as mcp:
            with self.assertRaises(ShopifyMcpError):
                mcp.list_tools()
        client.close()


if __name__ == "__main__":
    unittest.main()
