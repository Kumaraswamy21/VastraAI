"""Unit and DB tests for Gemini + pgvector semantic search."""

from __future__ import annotations

import math
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from fashion_search.embeddings.errors import EmbeddingConfigError, EmbeddingValidationError
from fashion_search.embeddings.gemini import TASK_QUERY, validate_embedding
from fashion_search.search.schemas import SemanticSearchRequest
from fashion_search.search.semantic import (
    SemanticSearchError,
    hit_from_row,
    normalize_query,
    semantic_search,
)
from fashion_search.search.vector import VectorHit


def database_url_configured() -> bool:
    return bool(os.environ.get("DATABASE_URL") or os.path.exists(".env") or os.path.exists("../.env"))


def unit_vector(values: list[float]) -> list[float]:
    return validate_embedding(values, expected_dimensions=len(values))


class QueryValidationTests(unittest.TestCase):
    def test_blank_query_rejected(self) -> None:
        with self.assertRaises(SemanticSearchError):
            normalize_query("   ")
        with self.assertRaises(ValidationError):
            SemanticSearchRequest(query="   ")

    def test_limit_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            SemanticSearchRequest(query="red shirt", limit=0)
        with self.assertRaises(ValidationError):
            SemanticSearchRequest(query="red shirt", limit=99)
        ok = SemanticSearchRequest(query="red cotton shirt for men", limit=10)
        self.assertEqual(ok.limit, 10)


class SemanticServiceTests(unittest.TestCase):
    def test_embed_query_uses_retrieval_query_task(self) -> None:
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
        )
        embedder = MagicMock()
        embedder.embed_query.return_value = [1.0, 0.0]
        product = SimpleNamespace(
            id=1,
            title="Red Shirt",
            category="shirt",
            color="red",
            material="cotton",
            style="slim fit",
            gender="men",
            occasion="casual",
            price_inr=1299,
            image_reference="catalog/x.webp",
            slug="red-shirt",
        )
        with patch(
            "fashion_search.search.semantic.search_by_vector",
            return_value=[VectorHit(product=product, similarity_score=0.91)],
        ) as search:
            response = semantic_search(
                SemanticSearchRequest(query="red cotton shirt for men", limit=5),
                settings=settings,
                embedder=embedder,
            )
        embedder.embed_query.assert_called_once_with("red cotton shirt for men")
        search.assert_called_once()
        self.assertEqual(response.total, 1)
        self.assertEqual(response.results[0].similarity_score, 0.91)
        self.assertEqual(response.results[0].product_url, "/products/red-shirt")
        self.assertNotIn("embedding", response.results[0].model_dump())

    def test_gemini_validation_maps_to_422(self) -> None:
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
        )
        embedder = MagicMock()
        embedder.embed_query.side_effect = EmbeddingValidationError("empty")
        with self.assertRaises(SemanticSearchError) as ctx:
            semantic_search(
                SemanticSearchRequest(query="ok"),
                settings=settings,
                embedder=embedder,
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_gemini_config_maps_to_502(self) -> None:
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=768,
        )
        embedder = MagicMock()
        embedder.embed_query.side_effect = EmbeddingConfigError("missing key")
        with self.assertRaises(SemanticSearchError) as ctx:
            semantic_search(
                SemanticSearchRequest(query="ok"),
                settings=settings,
                embedder=embedder,
            )
        self.assertEqual(ctx.exception.status_code, 502)

    def test_empty_results(self) -> None:
        settings = SimpleNamespace(
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
        )
        embedder = MagicMock()
        embedder.embed_query.return_value = [0.0, 1.0]
        with patch("fashion_search.search.semantic.search_by_vector", return_value=[]):
            response = semantic_search(
                SemanticSearchRequest(query="purple neon boots"),
                settings=settings,
                embedder=embedder,
            )
        self.assertEqual(response.total, 0)
        self.assertEqual(response.results, [])

    def test_hit_metadata_excludes_internal_fields(self) -> None:
        product = SimpleNamespace(
            id=9,
            title="Kurta",
            category="kurta",
            color="black",
            material="cotton",
            style="classic",
            gender="men",
            occasion="festive",
            price_inr=1999,
            image_reference="catalog/k.webp",
            slug="black-kurta",
            embedding=[0.1] * 768,
            embedding_text_hash="abc",
        )
        hit = hit_from_row(VectorHit(product=product, similarity_score=0.88))
        payload = hit.model_dump()
        self.assertEqual(payload["currency"], "INR")
        self.assertNotIn("embedding", payload)
        self.assertNotIn("embedding_text_hash", payload)


class GeminiQueryTaskTests(unittest.TestCase):
    def test_embed_query_passes_task_type(self) -> None:
        from fashion_search.embeddings.gemini import GeminiEmbedder

        settings = SimpleNamespace(
            gemini_api_key="k",
            google_api_key="",
            embedding_model="gemini-embedding-001",
            embedding_dimensions=2,
            embedding_batch_size=16,
            embedding_max_retries=0,
        )
        client = MagicMock()
        client.models.embed_content.return_value = SimpleNamespace(
            embeddings=[SimpleNamespace(values=[1.0, 0.0])]
        )
        embedder = GeminiEmbedder(settings=settings, client=client)
        embedder.embed_query("red shirt")
        kwargs = client.models.embed_content.call_args.kwargs
        self.assertEqual(kwargs["config"].task_type, TASK_QUERY)


@unittest.skipUnless(database_url_configured(), "DATABASE_URL required")
class PgvectorSearchTests(unittest.TestCase):
    """Integration tests using deterministic vectors (no live Gemini calls)."""

    @classmethod
    def setUpClass(cls) -> None:
        from fashion_search.config.settings import get_settings
        from fashion_search.core.db import get_engine
        from sqlalchemy import text

        cls.settings = get_settings()
        cls.engine = get_engine()
        with cls.engine.connect() as connection:
            ext = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            if ext != "vector":
                raise unittest.SkipTest("pgvector extension is not available")
            cls.product_ids = [
                row[0]
                for row in connection.execute(
                    text("SELECT id FROM products ORDER BY id ASC LIMIT 3")
                ).all()
            ]
        if len(cls.product_ids) < 3:
            raise unittest.SkipTest("need at least 3 products for vector ordering tests")

    def setUp(self) -> None:
        from sqlalchemy import text

        dims = self.settings.embedding_dimensions
        # Orthogonal-ish unit vectors in the first three dimensions.
        vectors = {
            self.product_ids[0]: unit_vector([1.0] + [0.0] * (dims - 1)),
            self.product_ids[1]: unit_vector([0.0, 1.0] + [0.0] * (dims - 2)),
            self.product_ids[2]: unit_vector([0.0, 0.0, 1.0] + [0.0] * (dims - 3)),
        }
        with self.engine.begin() as connection:
            for product_id, vector in vectors.items():
                connection.execute(
                    text(
                        """
                        UPDATE products
                        SET embedding = CAST(:embedding AS vector),
                            embedding_provider = 'gemini',
                            embedding_model = :model,
                            embedding_dimensions = :dims,
                            embedding_status = 'COMPLETED',
                            embedding_error = NULL,
                            embedding_text_hash = 'test-hash'
                        WHERE id = :id
                        """
                    ),
                    {
                        "embedding": str(vector),
                        "model": self.settings.embedding_model,
                        "dims": dims,
                        "id": product_id,
                    },
                )
        self.vectors = vectors

    def tearDown(self) -> None:
        from sqlalchemy import bindparam, text

        statement = text(
            """
            UPDATE products
            SET embedding = NULL,
                embedding_provider = NULL,
                embedding_model = NULL,
                embedding_dimensions = NULL,
                embedding_status = 'PENDING',
                embedding_text_hash = NULL,
                embedding_error = NULL
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        with self.engine.begin() as connection:
            connection.execute(statement, {"ids": self.product_ids})

    def test_cosine_ordering(self) -> None:
        from fashion_search.search.vector import search_by_vector

        query = self.vectors[self.product_ids[0]]
        hits = search_by_vector(query, limit=3, settings=self.settings)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0].product.id, self.product_ids[0])
        self.assertAlmostEqual(hits[0].similarity_score, 1.0, places=5)
        scores = [hit.similarity_score for hit in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_incompatible_model_excluded(self) -> None:
        from fashion_search.search.vector import search_by_vector
        from sqlalchemy import text

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE products
                    SET embedding_model = 'other-model'
                    WHERE id = :id
                    """
                ),
                {"id": self.product_ids[0]},
            )
        hits = search_by_vector(
            self.vectors[self.product_ids[0]],
            limit=10,
            settings=self.settings,
        )
        ids = {hit.product.id for hit in hits}
        self.assertNotIn(self.product_ids[0], ids)

    def test_semantic_endpoint_with_mocked_gemini(self) -> None:
        from fashion_search.main import app

        client = TestClient(app)
        query_vector = self.vectors[self.product_ids[0]]
        with patch(
            "fashion_search.search.semantic.build_gemini_embedder"
        ) as build:
            embedder = MagicMock()
            embedder.embed_query.return_value = query_vector
            build.return_value = embedder
            response = client.post(
                "/search/semantic",
                json={"query": "red cotton shirt for men", "limit": 2},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "red cotton shirt for men")
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["results"][0]["product_id"], self.product_ids[0])
        self.assertNotIn("embedding", body["results"][0])

    def test_endpoint_rejects_empty_query(self) -> None:
        from fashion_search.main import app

        client = TestClient(app)
        response = client.post("/search/semantic", json={"query": "  "})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
