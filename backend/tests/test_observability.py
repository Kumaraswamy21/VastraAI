"""Deterministic provider, privacy, correlation, and dashboard telemetry tests."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fashion_search.ai.errors import AIProviderTimeoutError, AIProviderUnavailableError
from fashion_search.api.observability import router
from fashion_search.config.settings import Settings, get_settings
from fashion_search.generation.router import GenerationRouter
from fashion_search.observability.context import search_context
from fashion_search.observability.instrumentation import (
    InstrumentedEmbeddingProvider,
    InstrumentedGenerationProvider,
)
from fashion_search.observability.pricing import PricingCatalog
from fashion_search.observability.schemas import AIUsage
from fashion_search.search.schemas import HybridSearchResponse


def settings(**overrides):
    values = dict(
        database_url="postgresql://unused",
        gemini_api_key="test",
        observability_enabled=True,
        app_environment="development",
        observability_pricing_json="{}",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


class Collector:
    def __init__(self, fail: bool = False) -> None:
        self.events = []
        self.fail = fail

    def record_provider(self, event) -> None:
        if self.fail:
            raise RuntimeError("database down")
        self.events.append(event)


class FakeGenerator:
    name = "gemini"
    model_name = "gemini-test"

    def __init__(self, error=None, usage=None) -> None:
        self.error = error
        self.usage = usage or AIUsage()

    def generate(self, prompt, *, system_prompt=None):
        if self.error:
            raise self.error
        return "ok"

    def generate_structured(self, prompt, schema, *, system_prompt=None):
        if self.error:
            raise self.error
        return schema.model_validate({})

    def take_usage(self):
        return self.usage

    def health(self):
        return {}


class FakeEmbedder:
    name = "ollama"
    model_name = "nomic-test"
    dimensions = 2

    def embed_query(self, text):
        return [1.0, 0.0]

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def take_usage(self):
        return AIUsage()

    def health(self):
        return {}


class ProviderInstrumentationTests(unittest.TestCase):
    def test_success_records_identity_operation_latency_usage_and_cost(self) -> None:
        cfg = settings(
            observability_pricing_json='{"models":[{"provider":"gemini","model":"gemini-test","input_cost_per_million_tokens":"1","output_cost_per_million_tokens":"2","currency":"USD","effective_date":"2026-10-01"}]}'
        )
        collector = Collector()
        provider = InstrumentedGenerationProvider(
            FakeGenerator(
                usage=AIUsage(input_tokens=100, output_tokens=50, total_tokens=150)
            ),
            settings=cfg,
            telemetry=collector,
        )
        self.assertEqual(provider.generate("secret prompt"), "ok")
        event = collector.events[0]
        self.assertEqual(
            (event.provider, event.model, event.operation),
            ("gemini", "gemini-test", "generation"),
        )
        self.assertEqual(event.outcome, "SUCCESS")
        self.assertGreaterEqual(event.latency_ms, 0)
        self.assertEqual(event.total_tokens, 150)
        self.assertEqual(str(event.estimated_cost), "0.0002")
        self.assertNotIn("secret", str(event.model_dump()))

    def test_failures_are_normalized_and_reraised(self) -> None:
        for error, outcome in (
            (AIProviderTimeoutError("late"), "TIMEOUT"),
            (AIProviderUnavailableError("down"), "UNAVAILABLE"),
        ):
            with self.subTest(outcome=outcome):
                collector = Collector()
                provider = InstrumentedGenerationProvider(
                    FakeGenerator(error=error), settings=settings(), telemetry=collector
                )
                with self.assertRaises(type(error)):
                    provider.generate("x")
                self.assertEqual(collector.events[0].outcome, outcome)

    def test_embedding_operations_and_missing_usage_are_null(self) -> None:
        collector = Collector()
        provider = InstrumentedEmbeddingProvider(
            FakeEmbedder(), settings=settings(), telemetry=collector
        )
        provider.embed_query("query")
        provider.embed_documents(["a", "b"])
        self.assertEqual(
            [e.operation for e in collector.events],
            ["query_embedding", "document_embedding"],
        )
        self.assertTrue(all(e.total_tokens is None for e in collector.events))
        self.assertTrue(all(e.estimated_cost is None for e in collector.events))

    def test_ollama_never_reports_fake_zero_cost(self) -> None:
        catalog = PricingCatalog(
            settings(
                observability_pricing_json='{"models":[{"provider":"ollama","model":"nomic-test","embedding_cost_per_million_tokens":"1","effective_date":"2026-10-01"}]}'
            )
        )
        self.assertEqual(
            catalog.estimate(
                "ollama", "nomic-test", "query_embedding", AIUsage(total_tokens=10)
            )[0],
            None,
        )

    def test_fallback_attempts_share_correlation_and_are_separate(self) -> None:
        collector = Collector()
        primary = InstrumentedGenerationProvider(
            FakeGenerator(error=AIProviderUnavailableError("down")),
            settings=settings(),
            telemetry=collector,
        )
        fallback_raw = FakeGenerator()
        fallback_raw.name = "ollama"
        fallback_raw.model_name = "gemma-test"
        fallback = InstrumentedGenerationProvider(
            fallback_raw, settings=settings(), telemetry=collector
        )
        router = GenerationRouter(
            primary=primary, fallback=fallback, settings=settings()
        )
        with search_context("search-123"):
            self.assertEqual(router.generate("x"), "ok")
        self.assertEqual(len(collector.events), 2)
        self.assertEqual(
            {e.search_request_id for e in collector.events}, {"search-123"}
        )
        self.assertFalse(collector.events[0].fallback_used)
        self.assertTrue(collector.events[1].fallback_used)

    def test_telemetry_failure_is_logged_and_does_not_change_result(self) -> None:
        provider = InstrumentedGenerationProvider(
            FakeGenerator(), settings=settings(), telemetry=Collector(fail=True)
        )
        with self.assertLogs(
            "fashion_search.observability.instrumentation", level="WARNING"
        ) as logs:
            self.assertEqual(provider.generate("x"), "ok")
        self.assertIn("telemetry_provider_write_failed", " ".join(logs.output))


class DashboardApiTests(unittest.TestCase):
    def app(self, cfg=None):
        app = FastAPI()
        app.include_router(router)
        if cfg:
            app.dependency_overrides[get_settings] = lambda: cfg
        return TestClient(app)

    def test_production_access_is_hidden(self) -> None:
        response = self.app(settings(app_environment="production")).get(
            "/dev/observability/summary"
        )
        self.assertEqual(response.status_code, 404)

    def test_summary_filters_and_request_detail(self) -> None:
        repo = MagicMock()
        repo.summary.return_value = {"ai_requests": 2, "ai_successes": 1}
        repo.providers.return_value = [{"provider": "gemini", "requests": 2}]
        repo.recent_providers.return_value = []
        repo.request_detail.return_value = {
            "search": {"request_id": "abc"},
            "provider_events": [],
        }
        client = self.app(settings())
        with patch("fashion_search.api.observability.repository", repo):
            summary = client.get("/dev/observability/summary?range=1h")
            providers = client.get(
                "/dev/observability/providers?provider=gemini&outcome=SUCCESS"
            )
            detail = client.get("/dev/observability/requests/abc")
        self.assertEqual(summary.json()["ai_requests"], 2)
        self.assertEqual(providers.json()["breakdown"][0]["provider"], "gemini")
        filters = repo.providers.call_args.args[1]
        self.assertEqual(filters["provider"], "gemini")
        self.assertEqual(filters["outcome"], "SUCCESS")
        self.assertEqual(detail.json()["search"]["request_id"], "abc")


class SearchTelemetryTests(unittest.TestCase):
    def test_search_stages_counts_mode_and_privacy_are_recorded(self) -> None:
        from fashion_search.api.search import _record_search

        result = HybridSearchResponse(
            query="private wedding query",
            retrieval_query="dress",
            filters={},
            total=3,
            results=[],
            search_mode="keyword_fallback",
            semantic_search_available=False,
            metrics={
                "parse_ms": 4.0,
                "embed_ms": 5.0,
                "semantic_ms": 6.0,
                "keyword_ms": 7.0,
                "fusion_ms": 1.0,
                "explanation_ms": 2.0,
                "semantic_candidates": 8,
                "keyword_candidates": 9,
                "fallback": "keyword_only",
            },
        )
        sink = MagicMock()
        with (
            patch("fashion_search.api.search.telemetry_repository", sink),
            patch(
                "fashion_search.api.search.get_settings",
                return_value=settings(observability_store_raw_queries=False),
            ),
        ):
            _record_search(
                result,
                started=time.perf_counter(),
                session_id="session",
                query=result.query,
            )
        event = sink.record_search.call_args.args[0]
        self.assertEqual(event.search_mode, "KEYWORD_FALLBACK")
        self.assertTrue(event.fallback_used)
        self.assertFalse(event.semantic_search_available)
        self.assertEqual(event.semantic_candidate_count, 8)
        self.assertEqual(event.keyword_candidate_count, 9)
        self.assertEqual(event.final_result_count, 3)
        self.assertIsNotNone(event.query_hash)
        self.assertIsNone(event.redacted_query)

    def test_zero_results_and_failure_are_distinct(self) -> None:
        from fashion_search.api.search import _record_search

        sink = MagicMock()
        empty = HybridSearchResponse(
            query="x",
            retrieval_query="x",
            filters={},
            total=0,
            results=[],
            search_status="no_exact_matches",
        )
        with (
            patch("fashion_search.api.search.telemetry_repository", sink),
            patch("fashion_search.api.search.get_settings", return_value=settings()),
        ):
            _record_search(
                empty, started=time.perf_counter(), session_id=None, query="x"
            )
            _record_search(
                None,
                started=time.perf_counter(),
                session_id=None,
                query="x",
                error_type="SEARCH_ERROR",
            )
        events = [call.args[0] for call in sink.record_search.call_args_list]
        self.assertEqual(
            [event.outcome for event in events], ["ZERO_RESULTS", "FAILED"]
        )
        self.assertEqual(events[1].error_type, "SEARCH_ERROR")


class OverheadTests(unittest.TestCase):
    def test_in_process_wrapper_overhead_is_measured(self) -> None:
        iterations = 5000
        raw = FakeGenerator()
        wrapped = InstrumentedGenerationProvider(
            raw, settings=settings(), telemetry=Collector()
        )
        start = time.perf_counter()
        for _ in range(iterations):
            raw.generate("x")
        baseline = time.perf_counter() - start
        start = time.perf_counter()
        for _ in range(iterations):
            wrapped.generate("x")
        instrumented = time.perf_counter() - start
        overhead_us = max(0.0, instrumented - baseline) * 1_000_000 / iterations
        print(f"observability_wrapper_overhead_us={overhead_us:.2f}")
        self.assertGreaterEqual(overhead_us, 0)


if __name__ == "__main__":
    unittest.main()
