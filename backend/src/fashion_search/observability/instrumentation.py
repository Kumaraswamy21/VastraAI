"""Provider-boundary wrappers that preserve provider behavior."""

from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from fashion_search.ai.errors import (
    AIProviderAuthenticationError, AIProviderRateLimitError, AIProviderResponseError,
    AIProviderTimeoutError, AIProviderUnavailableError, EmbeddingDimensionError,
)
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.generation.base import AsyncGenerationMixin, GenerationProvider
from fashion_search.embeddings.base import AsyncEmbeddingMixin, EmbeddingProvider
from fashion_search.observability.context import (
    fallback_used_var, request_id, search_request_id_var,
)
from fashion_search.observability.pricing import PricingCatalog
from fashion_search.observability.repository import TelemetryRepository, repository
from fashion_search.observability.schemas import AIProviderEventData, AIUsage

T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


def normalize_error(exc: Exception) -> tuple[str, str, str | None]:
    if isinstance(exc, AIProviderTimeoutError):
        return "TIMEOUT", "PROVIDER_TIMEOUT", None
    if isinstance(exc, AIProviderRateLimitError):
        return "RATE_LIMITED", "PROVIDER_RATE_LIMIT", "429"
    if isinstance(exc, AIProviderAuthenticationError):
        return "FAILED", "AUTHENTICATION_ERROR", None
    if isinstance(exc, EmbeddingDimensionError):
        return "INVALID_RESPONSE", "EMBEDDING_DIMENSION_ERROR", None
    if isinstance(exc, AIProviderUnavailableError):
        return "UNAVAILABLE", "PROVIDER_UNAVAILABLE", None
    if isinstance(exc, AIProviderResponseError):
        return "INVALID_RESPONSE", "INVALID_PROVIDER_RESPONSE", None
    return "FAILED", type(exc).__name__.upper(), None


class _Instrumented:
    def __init__(self, provider: Any, *, settings: Settings | None, telemetry: TelemetryRepository | None) -> None:
        self._provider = provider
        self._settings = settings or get_settings()
        self._telemetry = telemetry or repository
        self._pricing = PricingCatalog(self._settings)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    @property
    def __class__(self):  # Preserve compatibility with provider-type introspection.
        return self._provider.__class__

    def _call(self, operation: str, function, *args, metadata: dict[str, Any] | None = None, **kwargs):
        started = time.perf_counter()
        usage = AIUsage()
        outcome, error_type, error_code = "SUCCESS", None, None
        try:
            result = function(*args, **kwargs)
            take_usage = getattr(self._provider, "take_usage", None)
            if callable(take_usage):
                usage = take_usage() or AIUsage()
            return result
        except Exception as exc:
            take_usage = getattr(self._provider, "take_usage", None)
            if callable(take_usage):
                usage = take_usage() or AIUsage()
            outcome, error_type, error_code = normalize_error(exc)
            raise
        finally:
            latency = (time.perf_counter() - started) * 1000
            estimated, currency, effective = self._pricing.estimate(
                self.name, self.model_name, operation, usage
            )
            event = AIProviderEventData(
                request_id=request_id(), search_request_id=search_request_id_var.get(),
                provider=self.name, model=self.model_name, operation=operation,
                outcome=outcome, latency_ms=latency,
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens, estimated_cost=estimated,
                cost_currency=currency, pricing_effective_date=effective,
                error_type=error_type, error_code=error_code,
                fallback_used=fallback_used_var.get(), metadata=metadata or {},
            )
            try:
                self._telemetry.record_provider(event)
            except Exception as exc:
                logger.warning("telemetry_provider_write_failed error_type=%s", type(exc).__name__)


class InstrumentedGenerationProvider(_Instrumented, AsyncGenerationMixin):
    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return self._call("generation", self._provider.generate, prompt, system_prompt=system_prompt)

    def generate_structured(self, prompt: str, schema: type[T], *, system_prompt: str | None = None) -> T:
        return self._call(
            "structured_generation", self._provider.generate_structured,
            prompt, schema, system_prompt=system_prompt,
            metadata={"response_schema": schema.__name__},
        )

    def health(self) -> dict[str, object]:
        return self._provider.health()


class InstrumentedEmbeddingProvider(_Instrumented, AsyncEmbeddingMixin):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call(
            "document_embedding", self._provider.embed_documents, texts,
            metadata={"document_count": len(texts)},
        )

    def embed_query(self, text: str) -> list[float]:
        return self._call("query_embedding", self._provider.embed_query, text)

    def health(self) -> dict[str, object]:
        return self._provider.health()


def instrument_generation_provider(
    provider: GenerationProvider, settings: Settings | None = None,
    telemetry: TelemetryRepository | None = None,
) -> GenerationProvider:
    cfg = settings or get_settings()
    if not getattr(cfg, "observability_enabled", False):
        return provider
    return InstrumentedGenerationProvider(provider, settings=cfg, telemetry=telemetry)


def instrument_embedding_provider(
    provider: EmbeddingProvider, settings: Settings | None = None,
    telemetry: TelemetryRepository | None = None,
) -> EmbeddingProvider:
    cfg = settings or get_settings()
    if not getattr(cfg, "observability_enabled", False):
        return provider
    return InstrumentedEmbeddingProvider(provider, settings=cfg, telemetry=telemetry)
