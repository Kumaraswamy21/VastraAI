"""Safety tests for RAG answers grounded in live Shopify search results."""

from __future__ import annotations

import unittest

from fashion_search.config.settings import Settings
from fashion_search.rag.shopify import (
    ShopifyGroundedGeneration,
    generate_shopify_grounded_answer,
)
from fashion_search.shopify.schemas import ShopifyProductResult


def settings() -> Settings:
    return Settings(_env_file=None, database_url="postgresql://unused")


def product(**overrides) -> ShopifyProductResult:
    values = {
        "product_id": "gid://shopify/p/cotton-kurta",
        "title": "Cotton kurta",
        "description": "Soft cotton for warm days",
        "product_url": "https://shop.example/products/kurta",
        "price_min": "699",
        "price_max": "799",
        "currency": "INR",
        "merchant_name": "Example Shop",
        "available": True,
        "variants": [{"title": "Medium", "options": [{"name": "Size", "label": "M"}]}],
    }
    values.update(overrides)
    return ShopifyProductResult(**values)


class FakeProvider:
    name = "test"
    model_name = "test-model"

    def __init__(self, generated=None, error: Exception | None = None):
        self.generated = generated
        self.error = error

    def generate_structured(self, prompt, schema, *, system_prompt=None):
        self.prompt = prompt
        self.schema = schema
        if self.error:
            raise self.error
        return self.generated


class ShopifyRagTests(unittest.TestCase):
    def test_gemini_compatible_schema_omits_unsupported_json_schema_keyword(self):
        schema = ShopifyGroundedGeneration.model_json_schema()
        self.assertNotIn("additionalProperties", schema)
        self.assertNotIn("additionalProperties", schema["$defs"]["ShopifyGroundedClaim"])

    def test_answer_uses_only_values_from_bounded_live_product_context(self):
        provider = FakeProvider(
            ShopifyGroundedGeneration(
                answer_kind="comparison",
                referenced_product_ids=["gid://shopify/p/cotton-kurta"],
                claims=[
                    {
                        "product_id": "gid://shopify/p/cotton-kurta",
                        "attribute": "description",
                        "value": "Soft cotton for warm days",
                    },
                    {
                        "product_id": "gid://shopify/p/cotton-kurta",
                        "attribute": "variant",
                        "value": "Size: M",
                    },
                ],
            )
        )
        result = generate_shopify_grounded_answer(
            "Which option is breathable?", [product()], settings=settings(), provider=provider
        )

        self.assertIn("Soft cotton for warm days", result.answer)
        self.assertNotIn("title is", result.answer)
        self.assertNotIn("description is Cotton kurta", result.answer)
        self.assertIn("Cotton kurta — description: Soft cotton for warm days", result.answer)
        self.assertEqual(result.referenced_product_ids, ["gid://shopify/p/cotton-kurta"])
        self.assertEqual(result.context_count, 1)
        self.assertIn('"price":"699 INR to 799 INR"', provider.prompt)

    def test_invented_claim_is_rejected_and_safe_answer_is_returned(self):
        provider = FakeProvider(
            ShopifyGroundedGeneration(
                answer_kind="summary",
                referenced_product_ids=["gid://shopify/p/cotton-kurta"],
                claims=[
                    {
                        "product_id": "gid://shopify/p/cotton-kurta",
                        "attribute": "description",
                        "value": "Pure organic cotton",
                    }
                ],
            )
        )
        result = generate_shopify_grounded_answer(
            "Is this organic?", [product()], settings=settings(), provider=provider
        )

        self.assertTrue(result.grounding_failure)
        self.assertFalse(result.invalid_product_reference)
        self.assertEqual(result.answer, "I found 1 live Shopify option matching your preferences.")

    def test_exact_price_endpoint_from_live_range_is_accepted(self):
        provider = FakeProvider(
            ShopifyGroundedGeneration(
                answer_kind="summary",
                referenced_product_ids=["gid://shopify/p/cotton-kurta"],
                claims=[
                    {
                        "product_id": "gid://shopify/p/cotton-kurta",
                        "attribute": "price",
                        "value": "699 INR",
                    }
                ],
            )
        )
        result = generate_shopify_grounded_answer(
            "What is the lowest price?", [product()], settings=settings(), provider=provider
        )

        self.assertFalse(result.grounding_failure)
        self.assertIn("listed price: 699 INR", result.answer)

    def test_verbatim_excerpt_from_live_description_is_accepted(self):
        provider = FakeProvider(
            ShopifyGroundedGeneration(
                answer_kind="summary",
                referenced_product_ids=["gid://shopify/p/cotton-kurta"],
                claims=[
                    {
                        "product_id": "gid://shopify/p/cotton-kurta",
                        "attribute": "description",
                        "value": "cotton for warm days",
                    }
                ],
            )
        )
        result = generate_shopify_grounded_answer(
            "Is this good for summer?", [product()], settings=settings(), provider=provider
        )

        self.assertFalse(result.grounding_failure)
        self.assertIn("description: cotton for warm days", result.answer)

    def test_invalid_reference_is_rejected(self):
        provider = FakeProvider(
            ShopifyGroundedGeneration(
                answer_kind="summary", referenced_product_ids=["gid://shopify/p/other"]
            )
        )
        result = generate_shopify_grounded_answer(
            "Compare these", [product()], settings=settings(), provider=provider
        )

        self.assertTrue(result.grounding_failure)
        self.assertTrue(result.invalid_product_reference)

    def test_no_live_products_do_not_call_generation(self):
        provider = FakeProvider(error=AssertionError("should not be called"))
        result = generate_shopify_grounded_answer(
            "Which is best?", [], settings=settings(), provider=provider
        )
        self.assertEqual(result.answer, "")
        self.assertEqual(result.context_count, 0)


if __name__ == "__main__":
    unittest.main()
