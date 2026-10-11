"""API tests for selecting the independent Shopify search provider."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from fashion_search.main import app
from fashion_search.shopify.mcp_client import (
    ShopifyMcpError,
    ShopifyMcpProtocolError,
    ShopifyMcpRateLimitError,
    ShopifyMcpTimeoutError,
)


class SearchProviderApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.settings = MagicMock()
        self.settings.shopify_catalog_enabled = True
        self.settings.shopify_catalog_country = "IN"
        self.settings.market_currency = "INR"

    def test_shopify_provider_uses_mcp_and_returns_mapped_products(self) -> None:
        product = {
            "id": "gid://shopify/p/kurta",
            "title": "Blue cotton kurta",
            "url": "https://shop.example/products/kurta",
            "price_range": {
                "min": {"amount": 129900, "currency": "INR"},
                "max": {"amount": 129900, "currency": "INR"},
            },
        }
        mcp_client = MagicMock()
        mcp_client.__enter__.return_value.search_catalog.return_value = {
            "products": [product],
            "pagination": {"has_next_page": True},
        }
        with (
            patch("fashion_search.api.search.get_settings", return_value=self.settings),
            patch(
                "fashion_search.api.search.ShopifyMcpClient",
                return_value=mcp_client,
            ),
        ):
            response = self.client.post(
                "/search?provider=shopify",
                json={"query": "blue cotton kurta", "limit": 4},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "blue cotton kurta")
        self.assertEqual(body["total"], 1)
        self.assertTrue(body["has_next_page"])
        self.assertEqual(body["results"][0]["product_id"], "gid://shopify/p/kurta")
        self.assertEqual(body["results"][0]["price_min"], "1299")
        self.assertEqual(
            body["results"][0]["product_url"],
            "https://shop.example/products/kurta",
        )
        mcp_client.__enter__.return_value.search_catalog.assert_called_once_with(
            "blue cotton kurta",
            limit=4,
            currency="INR",
            filters={"available": True, "ships_to": {"country": "IN"}},
        )

    def test_budget_and_availability_are_enforced_on_returned_products(self) -> None:
        def product(name, amount, *, currency="INR", available=True):
            return {
                "id": f"gid://shopify/p/{name}",
                "title": name,
                "url": f"https://shop.example/products/{name}",
                "price_range": {
                    "min": {"amount": amount, "currency": currency},
                    "max": {"amount": amount, "currency": currency},
                },
                "variants": [{"availability": {"available": available}}],
            }

        mcp_client = MagicMock()
        mcp_client.__enter__.return_value.search_catalog.return_value = {
            "products": [
                product("within-budget", 149900),
                product("at-exclusive-bound", 150000),
                product("over-budget", 200000),
                product("wrong-currency", 1000, currency="USD"),
                product("unavailable", 90000, available=False),
            ],
            "pagination": {"has_next_page": True},
        }
        with (
            patch("fashion_search.api.search.get_settings", return_value=self.settings),
            patch(
                "fashion_search.api.search.ShopifyMcpClient",
                return_value=mcp_client,
            ),
        ):
            response = self.client.post(
                "/search?provider=shopify",
                json={"query": "Blue cotton kurta under ₹1500", "limit": 5},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["product_id"] for item in response.json()["results"]],
            ["gid://shopify/p/within-budget"],
        )
        mcp_client.__enter__.return_value.search_catalog.assert_called_once_with(
            "Blue cotton kurta under ₹1500",
            limit=5,
            currency="INR",
            filters={
                "available": True,
                "ships_to": {"country": "IN"},
                "price": {"max": 150000},
            },
        )

    def test_empty_catalog_results_are_a_successful_empty_page(self) -> None:
        mcp_client = MagicMock()
        mcp_client.__enter__.return_value.search_catalog.return_value = {
            "products": [],
            "pagination": {"has_next_page": False},
        }
        with (
            patch("fashion_search.api.search.get_settings", return_value=self.settings),
            patch(
                "fashion_search.api.search.ShopifyMcpClient",
                return_value=mcp_client,
            ),
        ):
            response = self.client.post(
                "/search?provider=shopify", json={"query": "no matching item"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_timeout_rate_limit_and_unavailability_map_to_http_errors(self) -> None:
        errors = (
            (ShopifyMcpTimeoutError("timeout"), 504, None),
            (ShopifyMcpRateLimitError("limited", "5"), 429, "5"),
            (ShopifyMcpProtocolError("invalid response"), 502, None),
            (ShopifyMcpError("offline"), 503, None),
        )
        for error, expected_status, retry_after in errors:
            with self.subTest(status=expected_status):
                mcp_client = MagicMock()
                mcp_client.__enter__.return_value.search_catalog.side_effect = error
                with (
                    patch(
                        "fashion_search.api.search.get_settings",
                        return_value=self.settings,
                    ),
                    patch(
                        "fashion_search.api.search.ShopifyMcpClient",
                        return_value=mcp_client,
                    ),
                ):
                    response = self.client.post(
                        "/search?provider=shopify", json={"query": "kurta"}
                    )
                self.assertEqual(response.status_code, expected_status)
                if retry_after:
                    self.assertEqual(response.headers["retry-after"], retry_after)

    def test_session_refinement_is_rejected_for_stateless_shopify_provider(
        self,
    ) -> None:
        response = self.client.post(
            "/search?provider=shopify",
            json={
                "query": "kurta",
                "session_id": "existing-session",
                "expected_revision": 0,
                "message": "blue",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_disabled_provider_is_unavailable(self) -> None:
        self.settings.shopify_catalog_enabled = False
        with (
            patch("fashion_search.api.search.get_settings", return_value=self.settings),
            patch("fashion_search.api.search.ShopifyMcpClient") as mcp_client,
        ):
            response = self.client.post(
                "/search?provider=shopify", json={"query": "kurta"}
            )
        self.assertEqual(response.status_code, 503)
        mcp_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
