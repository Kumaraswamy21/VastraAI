"""Tests for adapting Shopify catalog products to the API response shape."""

from decimal import Decimal
import unittest

from fashion_search.shopify.schemas import map_shopify_product, map_shopify_products


class ShopifyProductMappingTests(unittest.TestCase):
    def test_maps_complete_product_without_changing_merchant_urls(self) -> None:
        original_product_url = "https://shop.example/products/blue-kurta?variant=7"
        original_merchant_url = "https://shop.example"
        mapped = map_shopify_product(
            {
                "id": "gid://shopify/p/blue-kurta",
                "title": "Blue cotton kurta",
                "url": original_product_url,
                "description": {"html": "<p>Soft cotton</p>"},
                "price_range": {
                    "min": {"amount": 129900, "currency": "INR"},
                    "max": {"amount": 149900, "currency": "INR"},
                },
                "media": [
                    {
                        "type": "image",
                        "url": "https://cdn.example/kurta.jpg",
                        "alt_text": "Blue kurta",
                    }
                ],
                "variants": [
                    {
                        "id": "gid://shopify/ProductVariant/7",
                        "title": "Medium",
                        "seller": {
                            "name": "Example Shop",
                            "domain": "shop.example",
                            "url": original_merchant_url,
                        },
                        "availability": {"available": True},
                    }
                ],
            }
        )

        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped.product_id, "gid://shopify/p/blue-kurta")
        self.assertEqual(mapped.title, "Blue cotton kurta")
        self.assertEqual(mapped.description, "Soft cotton")
        self.assertEqual(mapped.product_url, original_product_url)
        self.assertEqual(mapped.merchant_url, original_merchant_url)
        self.assertEqual(mapped.price_min, Decimal("1299"))
        self.assertEqual(mapped.price_max, Decimal("1499"))
        self.assertEqual(mapped.currency, "INR")
        self.assertEqual(mapped.merchant_name, "Example Shop")
        self.assertEqual(mapped.merchant_domain, "shop.example")
        self.assertTrue(mapped.available)
        self.assertEqual(mapped.variants[0]["id"], "gid://shopify/ProductVariant/7")

    def test_missing_optional_fields_are_left_empty(self) -> None:
        mapped = map_shopify_product(
            {"id": "gid://shopify/p/plain", "title": "Plain product"}
        )

        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertIsNone(mapped.description)
        self.assertIsNone(mapped.product_url)
        self.assertIsNone(mapped.image_url)
        self.assertIsNone(mapped.price_min)
        self.assertIsNone(mapped.price_max)
        self.assertIsNone(mapped.currency)
        self.assertIsNone(mapped.merchant_name)
        self.assertIsNone(mapped.merchant_url)
        self.assertIsNone(mapped.available)
        self.assertIsNone(mapped.variants)

    def test_variant_product_url_is_used_when_product_url_is_missing(self) -> None:
        original_url = (
            "https://shop.example/products/item?variant=42&utm_source=shopify"
        )
        mapped = map_shopify_product(
            {
                "id": "gid://shopify/p/item",
                "title": "Item",
                "variants": [{"url": original_url}],
            }
        )
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped.product_url, original_url)

    def test_empty_or_missing_products_return_empty_list(self) -> None:
        self.assertEqual(map_shopify_products([]), [])
        self.assertEqual(map_shopify_products(None), [])

    def test_invalid_products_are_skipped(self) -> None:
        self.assertIsNone(map_shopify_product({"id": "", "title": "No ID"}))
        self.assertIsNone(map_shopify_product({"id": "gid://shopify/p/1", "title": 3}))
        self.assertIsNone(
            map_shopify_product(
                {
                    "id": "gid://shopify/p/1",
                    "title": "Bad URL",
                    "url": "javascript:alert(1)",
                }
            )
        )
        mapped = map_shopify_products(
            [None, "not a product", {"id": "gid://shopify/p/ok", "title": "Valid"}]
        )
        self.assertEqual([item.product_id for item in mapped], ["gid://shopify/p/ok"])

    def test_price_conversion_uses_each_currency_minor_unit_scale(self) -> None:
        for currency, amount, expected in (
            ("USD", 1299, Decimal("12.99")),
            ("JPY", 1299, Decimal("1299")),
            ("KWD", 1299, Decimal("1.299")),
        ):
            with self.subTest(currency=currency):
                mapped = map_shopify_product(
                    {
                        "id": f"gid://shopify/p/{currency.lower()}",
                        "title": "Item",
                        "price_range": {
                            "min": {"amount": amount, "currency": currency}
                        },
                    }
                )
                self.assertIsNotNone(mapped)
                assert mapped is not None
                self.assertEqual(mapped.currency, currency)
                self.assertEqual(mapped.price_min, expected)
                self.assertEqual(mapped.price_max, expected)


if __name__ == "__main__":
    unittest.main()
