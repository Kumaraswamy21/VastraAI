"""Provider contracts, switching, compatibility, and safe degradation."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from pydantic import BaseModel

from fashion_search.ai.errors import (
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    EmbeddingDimensionError,
)
from fashion_search.ai.factory import get_embedding_provider, get_generation_provider
from fashion_search.config.settings import Settings
from fashion_search.embeddings.gemini import GeminiEmbedder
from fashion_search.embeddings.ollama import OllamaEmbedder
from fashion_search.generation.gemini import GeminiGenerator
from fashion_search.generation.ollama import OllamaGemmaGenerator
from fashion_search.generation.router import GenerationRouter
from fashion_search.search.hybrid import hybrid_search
from fashion_search.search.keyword import KeywordHit
from fashion_search.search.schemas import FashionSearchConstraints, HybridSearchRequest


class StructuredValue(BaseModel):
    color: str


def settings(**overrides) -> Settings:
    values = dict(
        database_url="postgresql://unused",
        gemini_api_key="test",
        embedding_dimensions=2,
        ollama_embedding_dimensions=2,
        embedding_batch_size=2,
        generation_max_retries=0,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


class FakeResponse:
    def __init__(self, data, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://ollama/api")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failure", request=request, response=response)


class GenerationProviderContractTests(unittest.TestCase):
    def test_blank_fallback_configuration_disables_fallback(self) -> None:
        self.assertIsNone(settings(generation_fallback_provider="").generation_fallback_provider)

    def test_gemini_text_and_structured_generation(self) -> None:
        client = MagicMock()
        client.models.generate_content.side_effect = [
            SimpleNamespace(text="hello"),
            SimpleNamespace(parsed={"color": "black"}, text=""),
        ]
        provider = GeminiGenerator(settings(), client=client)
        self.assertEqual(provider.generate("hi"), "hello")
        self.assertEqual(
            provider.generate_structured("color", StructuredValue).color, "black"
        )

    def test_ollama_text_and_validated_structured_generation(self) -> None:
        client = MagicMock()
        client.post.side_effect = [
            FakeResponse({"response": "hello"}),
            FakeResponse({"response": '{"color":"black"}'}),
        ]
        provider = OllamaGemmaGenerator(settings(), client=client)
        self.assertEqual(provider.generate("hi"), "hello")
        self.assertEqual(
            provider.generate_structured("color", StructuredValue).color, "black"
        )

    def test_invalid_ollama_structured_output_is_rejected(self) -> None:
        client = MagicMock()
        client.post.return_value = FakeResponse({"response": '{"wrong":true}'})
        with self.assertRaises(AIProviderResponseError):
            OllamaGemmaGenerator(settings(), client=client).generate_structured(
                "color", StructuredValue
            )

    def test_ollama_timeout_and_unavailable_are_neutral_errors(self) -> None:
        for failure, expected in (
            (httpx.ReadTimeout("late"), AIProviderTimeoutError),
            (httpx.ConnectError("down"), AIProviderUnavailableError),
        ):
            client = MagicMock()
            client.post.side_effect = failure
            with self.assertRaises(expected):
                OllamaGemmaGenerator(settings(), client=client).generate("hi")

    def test_config_switching_and_async_compatibility(self) -> None:
        gemini = get_generation_provider(settings(generation_provider="gemini"))
        ollama = get_generation_provider(settings(generation_provider="ollama"))
        self.assertIsInstance(gemini, GeminiGenerator)
        self.assertIsInstance(ollama, OllamaGemmaGenerator)
        ollama.generate = MagicMock(return_value="async")
        self.assertEqual(asyncio.run(ollama.agenerate("hi")), "async")

    def test_configured_generation_fallback(self) -> None:
        primary = MagicMock(name="primary")
        primary.name = "gemini"
        primary.generate.side_effect = AIProviderUnavailableError("down")
        fallback = MagicMock(name="fallback")
        fallback.name = "ollama"
        fallback.generate.return_value = "local"
        router = GenerationRouter(primary=primary, fallback=fallback, settings=settings())
        self.assertEqual(router.generate("hi"), "local")


class EmbeddingProviderContractTests(unittest.TestCase):
    def test_gemini_documents_query_batch_and_identity(self) -> None:
        client = MagicMock()
        client.models.embed_content.side_effect = [
            SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 0.0]), SimpleNamespace(values=[0.0, 1.0])]),
            SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 0.0])]),
        ]
        provider = GeminiEmbedder(settings(), client=client)
        self.assertEqual(len(provider.embed_documents(["one", "two"])), 2)
        self.assertEqual(provider.embed_query("query"), [1.0, 0.0])
        self.assertEqual(provider.name, "gemini")
        self.assertEqual(provider.model_name, "gemini-embedding-001")

    def test_ollama_documents_query_batch_and_identity(self) -> None:
        client = MagicMock()
        client.post.side_effect = [
            FakeResponse({"embeddings": [[1.0, 0.0], [0.0, 1.0]]}),
            FakeResponse({"embeddings": [[1.0, 0.0]]}),
        ]
        provider = OllamaEmbedder(settings(), client=client)
        self.assertEqual(len(provider.embed_documents(["one", "two"])), 2)
        self.assertEqual(provider.embed_query("query"), [1.0, 0.0])
        self.assertEqual(provider.name, "ollama")

    def test_ollama_empty_input_and_dimension_validation(self) -> None:
        provider = OllamaEmbedder(settings(), client=MagicMock())
        self.assertEqual(provider.embed_documents([]), [])
        client = MagicMock()
        client.post.return_value = FakeResponse({"embeddings": [[1.0, 0.0, 0.0]]})
        with self.assertRaises(EmbeddingDimensionError):
            OllamaEmbedder(settings(), client=client).embed_query("query")

    def test_embedding_factory_switches_independently(self) -> None:
        self.assertIsInstance(
            get_embedding_provider(settings(embedding_provider="gemini")), GeminiEmbedder
        )
        self.assertIsInstance(
            get_embedding_provider(settings(embedding_provider="ollama")), OllamaEmbedder
        )


class CompatibilityAndDegradationTests(unittest.TestCase):
    @patch("fashion_search.search.hybrid.diagnose_zero_results")
    @patch("fashion_search.search.hybrid.search_by_keyword")
    @patch("fashion_search.search.hybrid.embedding_index_status", return_value="incompatible")
    @patch("fashion_search.search.hybrid.get_embedding_provider")
    @patch("fashion_search.search.hybrid.parse_constraints")
    def test_incompatible_index_skips_query_embedding_and_uses_keyword(
        self, parse, get_provider, index_status, keyword, diagnostics,
    ) -> None:
        constraints = FashionSearchConstraints(category="dress")
        parse.return_value = SimpleNamespace(constraints=constraints)
        provider = MagicMock()
        provider.name = "ollama"
        provider.model_name = "nomic-embed-text"
        provider.dimensions = 2
        get_provider.return_value = provider
        item = SimpleNamespace(
            id=1, title="Dress", category="dress", color="black", material="cotton",
            style="maxi", gender="women", occasion="casual", sizes=["M"],
            price_inr=1000, image_reference="x", slug="dress",
        )
        keyword.return_value = [KeywordHit(item, 0.4)]
        cfg = settings(
            embedding_provider="ollama", hybrid_candidate_limit=10,
            hybrid_rrf_k=60, hybrid_semantic_weight=0.6,
            hybrid_keyword_weight=0.4, search_diagnostics_enabled=True,
        )
        response = hybrid_search(HybridSearchRequest(query="dress"), settings=cfg)
        provider.embed_query.assert_not_called()
        self.assertEqual(response.search_mode, "keyword_fallback")
        self.assertFalse(response.semantic_search_available)
        self.assertEqual(response.embedding_index_status, "incompatible")
        self.assertEqual(response.total, 1)
        self.assertEqual(response.results[0].ranking.ranking_sources, ["keyword"])
        diagnostics.assert_not_called()


if __name__ == "__main__":
    unittest.main()
