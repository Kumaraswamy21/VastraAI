"""Regression tests for synthetic catalog generation and public schemas."""

import unittest

from pydantic import ValidationError

from fashion_search.catalog.generator import PROFILES, generate_catalog
from fashion_search.catalog.schemas import ProductCreate, ProductRecord


class CatalogGeneratorTests(unittest.TestCase):
    def test_default_catalog_is_deterministic_and_unique(self) -> None:
        first = generate_catalog()
        second = generate_catalog()

        self.assertEqual(first, second)
        self.assertEqual(len(first), 750)
        self.assertEqual(len({product.slug for product in first}), 750)

    def test_every_product_matches_a_category_gender_profile(self) -> None:
        allowed_pairs = {
            (profile.category, gender)
            for profile in PROFILES
            for gender in profile.genders
        }
        for product in generate_catalog():
            self.assertIn((product.category, product.gender), allowed_pairs)

    def test_count_outside_supported_range_is_rejected(self) -> None:
        for count in (499, 1001):
            with self.subTest(count=count), self.assertRaises(ValueError):
                generate_catalog(count=count)


class ProductSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.product = generate_catalog(count=500)[0]

    def test_product_record_builds_link_from_slug(self) -> None:
        record = ProductRecord(id=1, **self.product.model_dump())
        self.assertEqual(record.product_url, f"/products/{self.product.slug}")
        self.assertEqual(record.model_dump()["product_url"], record.product_url)

    def test_unknown_input_fields_are_rejected(self) -> None:
        payload = self.product.model_dump()
        payload["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            ProductCreate.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
