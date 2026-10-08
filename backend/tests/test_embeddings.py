"""Unit tests for Gemini product embeddings (no live API calls)."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fashion_search.embeddings.errors import EmbeddingConfigError, EmbeddingValidationError
from fashion_search.embeddings.gemini import (
    GeminiEmbedder,
    l2_normalize,
    validate_embedding,
)
from fashion_search.embeddings.normalize import normalize_product_text, text_hash
from fashion_search.embeddings.pipeline import run_embedding_pipeline
from fashion_search.embeddings.repository import needs_embedding


SAMPLE_PRODUCT = {
    "title": "Men's Slim Fit Cotton Shirt",
    "brand": "Roadster",
    "category": "Shirts",
    "color": "Red",
    "material": "Cotton",
    "style": "Slim Fit",
    "occasion": "casual",
    "gender": "men",
    "description": "A soft everyday shirt.",
}


class NormalizeTests(unittest.TestCase):
    def test_example_shape_and_deterministic_order(self) -> None:
        text = normalize_product_text(
            {
                "title": "Men's Slim Fit Cotton Shirt",
                "brand": "Roadster",
                "category": "Shirts",
                "color": "Red",
                "material": "Cotton",
                "style": "Slim Fit",
            }
        )
        self.assertEqual(
            text,
            "Roadster Men's Slim Fit Cotton Shirt. "
            "Category: Shirts. Color: Red. Material: Cotton. Style: Slim Fit.",
        )

    def test_missing_attributes_are_skipped(self) -> None:
        text = normalize_product_text({"title": "Plain Tee", "color": "black"})
        self.assertEqual(text, "Plain Tee. Color: black.")

    def test_html_and_whitespace_are_stripped(self) -> None:
        text = normalize_product_text(
            {
                "title": "  Festive   Kurta ",
                "description": "<p>Soft&nbsp;cotton</p>",
            }
        )
        self.assertEqual(text, "Festive Kurta. Soft cotton.")

    def test_identical_records_produce_identical_text_and_hash(self) -> None:
        first = normalize_product_text(SAMPLE_PRODUCT)
        second = normalize_product_text(dict(SAMPLE_PRODUCT))
        self.assertEqual(first, second)
        self.assertEqual(text_hash(first), text_hash(second))
        self.assertEqual(len(text_hash(first)), 64)

    def test_price_and_id_are_excluded(self) -> None:
        text = normalize_product_text(
            {
                "id": 99,
                "title": "Jacket",
                "price_inr": 1999,
                "sizes": ["M", "L"],
            }
        )
        self.assertEqual(text, "Jacket.")
        self.assertNotIn("1999", text)
        self.assertNotIn("99", text)


class GeminiValidationTests(unittest.TestCase):
    def test_validate_dimensions_and_normalize(self) -> None:
        vector = validate_embedding([3.0, 4.0], expected_dimensions=2)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in vector)), 1.0)
        self.assertAlmostEqual(vector[0], 0.6)
        self.assertAlmostEqual(vector[1], 0.8)

    def test_dimension_mismatch_is_rejected(self) -> None:
        with self.assertRaises(EmbeddingValidationError):
            validate_embedding([0.1, 0.2], expected_dimensions=768)

    def test_empty_input_is_rejected(self) -> None:
        settings = SimpleNamespace(
            gemini_api_key="test-key",
            google_api_key="",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_max_retries=0,
        )
        embedder = GeminiEmbedder(settings=settings, client=MagicMock())
        with self.assertRaises(EmbeddingValidationError):
            embedder.embed_texts(["   "])

    def test_successful_batch_parses_response(self) -> None:
        settings = SimpleNamespace(
            gemini_api_key="test-key",
            google_api_key="",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_max_retries=0,
        )
        client = MagicMock()
        client.models.embed_content.return_value = SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[3.0, 4.0]),
                SimpleNamespace(values=[0.0, 5.0]),
            ]
        )
        embedder = GeminiEmbedder(settings=settings, client=client)
        vectors = embedder.embed_texts(["one", "two"])
        self.assertEqual(len(vectors), 2)
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in vectors[0])), 1.0)
        self.assertEqual(embedder.api_request_count, 1)

    def test_rate_limit_retries_then_succeeds(self) -> None:
        settings = SimpleNamespace(
            gemini_api_key="test-key",
            google_api_key="",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_max_retries=2,
        )
        client = MagicMock()
        client.models.embed_content.side_effect = [
            RuntimeError("429 rate limit"),
            SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 0.0])]),
        ]
        embedder = GeminiEmbedder(settings=settings, client=client)
        with patch("fashion_search.embeddings.gemini.time.sleep"):
            vector = embedder.embed_text("ok")
        self.assertEqual(len(vector), 2)
        self.assertEqual(embedder.api_request_count, 2)

    def test_auth_failure_is_not_retried(self) -> None:
        settings = SimpleNamespace(
            gemini_api_key="bad",
            google_api_key="",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_max_retries=3,
        )
        client = MagicMock()
        client.models.embed_content.side_effect = RuntimeError("401 api key invalid")
        embedder = GeminiEmbedder(settings=settings, client=client)
        with self.assertRaises(EmbeddingConfigError):
            embedder.embed_text("ok")
        self.assertEqual(embedder.api_request_count, 1)

    def test_missing_api_key(self) -> None:
        settings = SimpleNamespace(
            gemini_api_key="",
            google_api_key="",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
            embedding_batch_size=16,
            embedding_max_retries=0,
        )
        embedder = GeminiEmbedder(settings=settings)
        with self.assertRaises(EmbeddingConfigError):
            embedder._api_key()


class NeedsEmbeddingTests(unittest.TestCase):
    def test_skip_when_completed_and_matching(self) -> None:
        product = SimpleNamespace(
            embedding=[0.1],
            embedding_status="COMPLETED",
            embedding_text_hash="abc",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
            embedding_provider="gemini",
        )
        self.assertFalse(
            needs_embedding(
                product,
                text_digest="abc",
                model="gemini-embedding-001",
                dimensions=768,
            )
        )

    def test_reembed_when_hash_or_model_changes(self) -> None:
        product = SimpleNamespace(
            embedding=[0.1],
            embedding_status="COMPLETED",
            embedding_text_hash="old",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
            embedding_provider="gemini",
        )
        self.assertTrue(
            needs_embedding(
                product,
                text_digest="new",
                model="gemini-embedding-001",
                dimensions=768,
            )
        )
        product.embedding_text_hash = "old"
        self.assertTrue(
            needs_embedding(
                product,
                text_digest="old",
                model="other-model",
                dimensions=768,
            )
        )

    def test_failed_records_are_retried(self) -> None:
        product = SimpleNamespace(
            embedding=None,
            embedding_status="FAILED",
            embedding_text_hash="abc",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
            embedding_provider="gemini",
        )
        self.assertTrue(
            needs_embedding(
                product,
                text_digest="abc",
                model="gemini-embedding-001",
                dimensions=768,
            )
        )


class PipelineTests(unittest.TestCase):
    def test_dry_run_does_not_call_gemini_or_write(self) -> None:
        product = SimpleNamespace(
            id=1,
            title="Kurta",
            category="kurta",
            color="black",
            material="cotton",
            style="classic",
            occasion="festive",
            gender="men",
            description="A festive cotton kurta.",
            embedding=None,
            embedding_status="PENDING",
            embedding_text_hash=None,
            embedding_model=None,
            embedding_dimensions=None,
            embedding_provider=None,
        )
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
            embedding_batch_size=16,
            embedding_stale_processing_minutes=30,
        )
        with (
            patch(
                "fashion_search.embeddings.pipeline.iter_product_batches",
                return_value=[[product]],
            ),
            patch("fashion_search.embeddings.pipeline.recover_stale_processing") as recover,
            patch("fashion_search.embeddings.pipeline.mark_processing") as mark,
            patch("fashion_search.embeddings.pipeline.save_completed") as save,
            patch("fashion_search.embeddings.pipeline.build_gemini_embedder") as build,
        ):
            stats = run_embedding_pipeline(dry_run=True, settings=settings)
        self.assertEqual(stats.inspected, 1)
        self.assertEqual(stats.required, 1)
        self.assertEqual(stats.skipped, 0)
        self.assertEqual(stats.embedded, 0)
        self.assertTrue(stats.dry_run)
        recover.assert_not_called()
        mark.assert_not_called()
        save.assert_not_called()
        build.assert_not_called()

    def test_pipeline_skips_unchanged_and_embeds_stale(self) -> None:
        fresh = SimpleNamespace(
            id=1,
            title="Fresh",
            category="shirt",
            color="white",
            material="cotton",
            style="solid",
            occasion="casual",
            gender="men",
            description="A white shirt for casual wear.",
            embedding=[0.1] * 2,
            embedding_status="COMPLETED",
            embedding_text_hash=None,
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_provider="gemini",
        )
        fresh_text = normalize_product_text(
            {
                "title": fresh.title,
                "category": fresh.category,
                "color": fresh.color,
                "material": fresh.material,
                "style": fresh.style,
                "occasion": fresh.occasion,
                "gender": fresh.gender,
                "description": fresh.description,
            }
        )
        fresh.embedding_text_hash = text_hash(fresh_text)

        stale = SimpleNamespace(
            id=2,
            title="Stale",
            category="shirt",
            color="blue",
            material="linen",
            style="slim fit",
            occasion="office",
            gender="men",
            description="A linen shirt for office wear.",
            embedding=None,
            embedding_status="PENDING",
            embedding_text_hash=None,
            embedding_model=None,
            embedding_dimensions=None,
            embedding_provider=None,
        )
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_stale_processing_minutes=30,
            gemini_api_key="test",
            google_api_key="",
            embedding_max_retries=0,
        )
        worker = MagicMock()
        worker.embed_texts.return_value = [[1.0, 0.0]]
        worker.api_request_count = 1

        with (
            patch(
                "fashion_search.embeddings.pipeline.iter_product_batches",
                return_value=[[fresh, stale]],
            ),
            patch("fashion_search.embeddings.pipeline.recover_stale_processing", return_value=0),
            patch("fashion_search.embeddings.pipeline.mark_processing") as mark,
            patch("fashion_search.embeddings.pipeline.save_completed") as save,
            patch("fashion_search.embeddings.pipeline.save_failed") as failed,
        ):
            stats = run_embedding_pipeline(
                dry_run=False,
                settings=settings,
                embedder=worker,
            )

        self.assertEqual(stats.inspected, 2)
        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.required, 1)
        self.assertEqual(stats.embedded, 1)
        self.assertEqual(stats.failed, 0)
        mark.assert_called_once()
        save.assert_called_once()
        failed.assert_not_called()
        worker.embed_texts.assert_called_once()

    def test_pipeline_idempotency_second_pass_skips(self) -> None:
        product = SimpleNamespace(
            id=7,
            title="Dupatta",
            category="dupatta",
            color="red",
            material="silk",
            style="printed",
            occasion="festive",
            gender="women",
            description="A festive silk dupatta.",
            embedding=[0.0, 1.0],
            embedding_status="COMPLETED",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_provider="gemini",
            embedding_text_hash="",
        )
        digest = text_hash(
            normalize_product_text(
                {
                    "title": product.title,
                    "category": product.category,
                    "color": product.color,
                    "material": product.material,
                    "style": product.style,
                    "occasion": product.occasion,
                    "gender": product.gender,
                    "description": product.description,
                }
            )
        )
        product.embedding_text_hash = digest
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_stale_processing_minutes=30,
        )
        with (
            patch(
                "fashion_search.embeddings.pipeline.iter_product_batches",
                return_value=[[product]],
            ),
            patch("fashion_search.embeddings.pipeline.recover_stale_processing", return_value=0),
            patch("fashion_search.embeddings.pipeline.build_gemini_embedder") as build,
        ):
            stats = run_embedding_pipeline(dry_run=False, settings=settings)
        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.required, 0)
        build.assert_not_called()


class L2Tests(unittest.TestCase):
    def test_zero_vector_rejected(self) -> None:
        with self.assertRaises(EmbeddingValidationError):
            l2_normalize([0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
