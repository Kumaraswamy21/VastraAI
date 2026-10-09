"""Unit and DB tests for hybrid FTS + semantic search."""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from fashion_search.search.constraints import fallback_parse
from fashion_search.search.filters import apply_search_constraints, constraints_currency_supported
from fashion_search.search.hybrid import hybrid_search
from fashion_search.search.keyword import search_by_keyword
from fashion_search.search.preprocess import build_retrieval_query
from fashion_search.search.ranking import reciprocal_rank_fusion
from fashion_search.search.schemas import FashionSearchConstraints, HybridSearchRequest
from fashion_search.search.vector import search_by_vector
from fashion_search.embeddings.errors import EmbeddingConfigError
from fashion_search.embeddings.gemini import validate_embedding


def database_url_configured() -> bool:
    return bool(os.environ.get("DATABASE_URL") or os.path.exists(".env") or os.path.exists("../.env"))


class RrfTests(unittest.TestCase):
    def test_rrf_prefers_items_in_both_lists(self) -> None:
        semantic = [(1, 0.9), (2, 0.8)]
        keyword = [(2, 0.5), (3, 0.4)]
        fused = reciprocal_rank_fusion(semantic, keyword, rrf_k=60, semantic_weight=0.6, keyword_weight=0.4)
        self.assertEqual(fused[0].product_id, 2)
        self.assertIsNotNone(fused[0].semantic_rank)
        self.assertIsNotNone(fused[0].keyword_rank)

    def test_results_sorted_by_score_then_product_id(self) -> None:
        semantic = [(1, 0.9), (2, 0.8), (3, 0.7)]
        keyword = [(2, 0.9), (3, 0.8), (1, 0.7)]
        fused = reciprocal_rank_fusion(semantic, keyword, rrf_k=60, semantic_weight=0.6, keyword_weight=0.4)
        for left, right in zip(fused, fused[1:], strict=False):
            if left.hybrid_score == right.hybrid_score:
                self.assertLess(left.product_id, right.product_id)
            else:
                self.assertGreater(left.hybrid_score, right.hybrid_score)

    def test_rrf_formula(self) -> None:
        semantic = [(10, 0.99)]
        keyword = []
        fused = reciprocal_rank_fusion(semantic, keyword, rrf_k=60, semantic_weight=0.6, keyword_weight=0.4)
        expected = 0.6 / (60 + 1)
        self.assertAlmostEqual(fused[0].hybrid_score, expected, places=9)


class PreprocessTests(unittest.TestCase):
    def test_strips_extracted_price_only(self) -> None:
        constraints = fallback_parse("black dress under ₹4000 for wedding")
        retrieval = build_retrieval_query("black dress under ₹4000 for wedding", constraints)
        self.assertIn("black", retrieval.lower())
        self.assertIn("dress", retrieval.lower())
        self.assertNotIn("4000", retrieval)
        self.assertNotIn("₹", retrieval)


class FilterTests(unittest.TestCase):
    def test_currency_guard(self) -> None:
        constraints = FashionSearchConstraints(currency="USD")
        self.assertFalse(constraints_currency_supported(constraints))

    def test_price_max_exclusive(self) -> None:
        from fashion_search.catalog.models import Product
        from sqlalchemy import select

        constraints = FashionSearchConstraints(
            color="black",
            price_max=Decimal("4000"),
            price_max_inclusive=False,
            currency="INR",
        )
        stmt = apply_search_constraints(select(Product), constraints)
        compiled = str(stmt.whereclause)
        self.assertIn("price_inr", compiled)


@unittest.skipUnless(database_url_configured(), "DATABASE_URL required")
class HybridIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from sqlalchemy import text

        from fashion_search.config.settings import get_settings
        from fashion_search.core.db import get_engine

        cls.settings = get_settings()
        cls.engine = get_engine()
        with cls.engine.connect() as connection:
            gin = connection.execute(
                text(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'products' AND indexname = 'products_search_vector_gin_idx'
                    """
                )
            ).scalar()
            if gin != "products_search_vector_gin_idx":
                raise unittest.SkipTest("FTS migration not applied")
            cls.product_id = connection.execute(
                text(
                    """
                    SELECT id FROM products
                    WHERE category = 'dress' AND color = 'black' AND price_inr < 4000
                    ORDER BY id ASC LIMIT 1
                    """
                )
            ).scalar()
            cls.overpriced_id = connection.execute(
                text(
                    """
                    SELECT id FROM products
                    WHERE category = 'dress' AND color = 'black' AND price_inr > 4000
                    ORDER BY id ASC LIMIT 1
                    """
                )
            ).scalar()

    def test_keyword_respects_black_dress_price_cap(self) -> None:
        constraints = fallback_parse("black dress under ₹4000")
        hits = search_by_keyword("black dress", constraints=constraints, limit=50)
        ids = {hit.product.id for hit in hits}
        if self.product_id:
            self.assertIn(self.product_id, ids)
        if self.overpriced_id:
            self.assertNotIn(self.overpriced_id, ids)
        for hit in hits:
            self.assertEqual(hit.product.color, "black")
            self.assertLessEqual(hit.product.price_inr, 4000)

    def test_vector_filter_excludes_overpriced_black_dress(self) -> None:
        if not self.product_id:
            self.skipTest("no black dress under 4000 in catalog")
        dims = self.settings.embedding_dimensions
        vector = validate_embedding([1.0] + [0.0] * (dims - 1), dims)
        constraints = fallback_parse("black dress under ₹4000")
        from sqlalchemy import text

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE products
                    SET embedding = CAST(:embedding AS vector),
                        embedding_provider = 'gemini',
                        embedding_model = :model,
                        embedding_dimensions = :dims,
                        embedding_status = 'COMPLETED'
                    WHERE id = :id
                    """
                ),
                {
                    "embedding": str(vector),
                    "model": self.settings.embedding_model,
                    "dims": dims,
                    "id": self.product_id,
                },
            )
        hits = search_by_vector(vector, limit=20, constraints=constraints, settings=self.settings)
        ids = {hit.product.id for hit in hits}
        self.assertIn(self.product_id, ids)
        if self.overpriced_id:
            self.assertNotIn(self.overpriced_id, ids)
        for hit in hits:
            self.assertLessEqual(hit.product.price_inr, 4000)

    def test_hybrid_endpoint_keyword_only_fallback(self) -> None:
        from fashion_search.main import app

        constraints = fallback_parse("black dress under ₹4000")
        client = TestClient(app)
        with patch("fashion_search.search.hybrid.parse_constraints") as parse:
            parse.return_value = SimpleNamespace(
                constraints=constraints,
                extraction_method="fallback",
                query="black dress under ₹4000",
            )
            with patch("fashion_search.search.hybrid.build_gemini_embedder") as build:
                embedder = MagicMock()
                embedder.embed_query.side_effect = EmbeddingConfigError("gemini down")
                build.return_value = embedder
                response = client.post(
                    "/search/hybrid",
                    json={"query": "black dress under ₹4000", "limit": 5},
                )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"]["fallback"], "keyword_only")
        for row in body["results"]:
            self.assertLessEqual(row["price_inr"], 4000)
            self.assertEqual(row["color"], "black")

    def test_post_search_alias(self) -> None:
        from fashion_search.main import app

        client = TestClient(app)
        with patch("fashion_search.api.search.hybrid_search") as search:
            search.return_value = SimpleNamespace(
                query="x",
                retrieval_query="x",
                filters={},
                total=0,
                results=[],
                metrics={},
            )
            response = client.post("/search", json={"query": "shirt", "limit": 3})
        self.assertEqual(response.status_code, 200)
        search.assert_called_once()


class HybridServiceTests(unittest.TestCase):
    def test_unsupported_currency_returns_empty(self) -> None:
        settings = SimpleNamespace(
            market_currency="INR",
            hybrid_candidate_limit=50,
            hybrid_rrf_k=60,
            hybrid_semantic_weight=0.6,
            hybrid_keyword_weight=0.4,
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
        )
        constraints = FashionSearchConstraints(currency="USD")
        with patch("fashion_search.search.hybrid.parse_constraints") as parse:
            parse.return_value = SimpleNamespace(
                constraints=constraints,
                extraction_method="fallback",
                query="dress",
            )
            response = hybrid_search(
                HybridSearchRequest(query="dress", limit=5),
                settings=settings,
                embedder=MagicMock(),
            )
        self.assertEqual(response.total, 0)


if __name__ == "__main__":
    unittest.main()
