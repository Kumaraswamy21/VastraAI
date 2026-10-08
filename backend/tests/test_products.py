"""Pagination, filter, and error tests for catalog browsing endpoints."""

import os
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from fashion_search.catalog.queries import ProductListQuery
from fashion_search.catalog.service import total_pages


def database_url_configured() -> bool:
    """True when tests can reach the configured PostgreSQL database."""
    return bool(os.environ.get("DATABASE_URL") or os.path.exists(".env") or os.path.exists("../.env"))


@unittest.skipUnless(database_url_configured(), "DATABASE_URL is required for catalog API tests")
class ProductApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fashion_search.main import app

        cls.client = TestClient(app)

    def test_page_zero_is_unprocessable(self) -> None:
        response = self.client.get("/products", params={"page": 0})
        self.assertEqual(response.status_code, 422)

    def test_page_size_zero_is_unprocessable(self) -> None:
        response = self.client.get("/products", params={"page_size": 0})
        self.assertEqual(response.status_code, 422)

    def test_page_size_above_max_is_unprocessable(self) -> None:
        response = self.client.get("/products", params={"page_size": 99})
        self.assertEqual(response.status_code, 422)

    def test_min_price_above_max_price_is_unprocessable(self) -> None:
        response = self.client.get("/products", params={"min_price": 5000, "max_price": 1000})
        self.assertEqual(response.status_code, 422)

    def test_default_page_is_first_page(self) -> None:
        response = self.client.get("/products")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 24)
        self.assertGreater(body["total_count"], 0)
        self.assertEqual(len(body["items"]), min(24, body["total_count"]))
        self.assertNotIn("embedding", body["items"][0])
        self.assertNotIn("search_vector", body["items"][0])

    def test_last_page_item_count_matches_remainder(self) -> None:
        first = self.client.get("/products", params={"page_size": 24}).json()
        last_page = first["total_pages"]
        response = self.client.get("/products", params={"page": last_page, "page_size": 24})
        self.assertEqual(response.status_code, 200)
        remainder = first["total_count"] % 24
        expected = 24 if remainder == 0 else remainder
        self.assertEqual(len(response.json()["items"]), expected)

    def test_page_past_end_returns_empty_items(self) -> None:
        first = self.client.get("/products", params={"page_size": 24}).json()
        past = first["total_pages"] + 5
        response = self.client.get("/products", params={"page": past, "page_size": 24})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"], [])
        self.assertEqual(body["total_count"], first["total_count"])
        self.assertEqual(body["page"], past)

    def test_exact_category_filter(self) -> None:
        sample = self.client.get("/products", params={"page_size": 1}).json()["items"][0]
        response = self.client.get("/products", params={"category": sample["category"], "page_size": 48})
        self.assertEqual(response.status_code, 200)
        for item in response.json()["items"]:
            self.assertEqual(item["category"], sample["category"])

    def test_combined_category_color_gender_filters(self) -> None:
        sample = self.client.get("/products", params={"page_size": 1}).json()["items"][0]
        response = self.client.get(
            "/products",
            params={
                "category": sample["category"],
                "color": sample["color"],
                "gender": sample["gender"],
                "page_size": 48,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(body["total_count"], 1)
        for item in body["items"]:
            self.assertEqual(item["category"], sample["category"])
            self.assertEqual(item["color"], sample["color"])
            self.assertEqual(item["gender"], sample["gender"])

    def test_size_filter_requires_containment(self) -> None:
        sample = self.client.get("/products", params={"page_size": 1}).json()["items"][0]
        size = sample["sizes"][0]
        response = self.client.get("/products", params={"size": size, "page_size": 48})
        self.assertEqual(response.status_code, 200)
        for item in response.json()["items"]:
            self.assertIn(size, item["sizes"])

    def test_price_range_is_inclusive(self) -> None:
        response = self.client.get("/products", params={"min_price": 1000, "max_price": 2500, "page_size": 48})
        self.assertEqual(response.status_code, 200)
        for item in response.json()["items"]:
            self.assertGreaterEqual(item["price_inr"], 1000)
            self.assertLessEqual(item["price_inr"], 2500)

    def test_price_sort_orders(self) -> None:
        asc = self.client.get("/products", params={"sort": "price_asc", "page_size": 10}).json()["items"]
        desc = self.client.get("/products", params={"sort": "price_desc", "page_size": 10}).json()["items"]
        asc_prices = [item["price_inr"] for item in asc]
        desc_prices = [item["price_inr"] for item in desc]
        self.assertEqual(asc_prices, sorted(asc_prices))
        self.assertEqual(desc_prices, sorted(desc_prices, reverse=True))

    def test_unknown_slug_is_not_found(self) -> None:
        response = self.client.get("/products/does-not-exist-slug")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_known_slug_omits_hidden_columns(self) -> None:
        sample = self.client.get("/products", params={"page_size": 1}).json()["items"][0]
        response = self.client.get(f"/products/{sample['slug']}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["slug"], sample["slug"])
        self.assertNotIn("embedding", body)
        self.assertNotIn("search_vector", body)
        self.assertEqual(body["product_url"], f"/products/{sample['slug']}")


class PaginationMathTests(unittest.TestCase):
    def test_empty_catalog_has_zero_pages(self) -> None:
        self.assertEqual(total_pages(0, 24), 0)

    def test_exact_page_boundary(self) -> None:
        self.assertEqual(total_pages(48, 24), 2)

    def test_partial_last_page(self) -> None:
        self.assertEqual(total_pages(49, 24), 3)


class ProductListQueryTests(unittest.TestCase):
    def test_inverted_price_range_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ProductListQuery(min_price=5000, max_price=100)


if __name__ == "__main__":
    unittest.main()
