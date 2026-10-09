"""Ollama HTTP adapter for document and query embeddings."""

from __future__ import annotations

import time
from typing import Any

import httpx

from fashion_search.ai.errors import (
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    EmbeddingDimensionError,
)
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.embeddings.base import (
    AsyncEmbeddingMixin,
    require_nonempty,
    validate_embedding,
)
from fashion_search.observability.schemas import AIUsage

logger = get_logger(__name__)


class OllamaEmbedder(AsyncEmbeddingMixin):
    """Ollama embeddings; query and document calls share one model/space."""

    name = "ollama"

    def __init__(
        self, settings: Settings | None = None, client: Any | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self.model_name = self._settings.ollama_embedding_model
        self.model = self.model_name
        self.dimensions = self._settings.ollama_embedding_dimensions
        self.batch_size = self._settings.embedding_batch_size
        self._client = client
        self.api_request_count = 0
        self._last_usage = AIUsage()

    def take_usage(self) -> AIUsage:
        usage, self._last_usage = self._last_usage, AIUsage()
        return usage

    def _http(self):
        return self._client or httpx.Client(
            base_url=self._settings.ollama_base_url,
            timeout=self._settings.ollama_timeout_seconds,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_text(self, text: str) -> list[float]:
        return self.embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [require_nonempty(text) for text in texts]
        results: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            results.extend(self._embed_chunk(cleaned[start : start + self.batch_size]))
        return results

    def _embed_chunk(self, texts: list[str]) -> list[list[float]]:
        started = time.perf_counter()
        try:
            self.api_request_count += 1
            response = self._http().post(
                "/api/embed", json={"model": self.model_name, "input": texts}
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            token_count = data.get("prompt_eval_count")
            self._last_usage = AIUsage(
                total_tokens=token_count if isinstance(token_count, int) else None
            )
            logger.info(
                "embedding_request provider=%s model=%s count=%s latency_ms=%.1f",
                self.name,
                self.model_name,
                len(texts),
                (time.perf_counter() - started) * 1000,
            )
        except httpx.TimeoutException as exc:
            logger.warning("embedding_failure provider=%s error=timeout", self.name)
            raise AIProviderTimeoutError("Ollama embedding request timed out") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            logger.warning("embedding_failure provider=%s error=unavailable", self.name)
            raise AIProviderUnavailableError("Ollama is unavailable") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise AIProviderUnavailableError(
                    "Ollama embedding model is unavailable"
                ) from exc
            raise AIProviderResponseError(
                f"Ollama HTTP {exc.response.status_code}"
            ) from exc
        except (ValueError, TypeError) as exc:
            raise AIProviderResponseError("Ollama returned invalid JSON") from exc
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise AIProviderResponseError(
                "Ollama returned an unexpected embedding count"
            )
        try:
            return [
                validate_embedding(vector, self.dimensions) for vector in embeddings
            ]
        except EmbeddingDimensionError:
            raise
        except Exception as exc:
            raise AIProviderResponseError("Ollama returned invalid embeddings") from exc

    def health(self) -> dict[str, object]:
        try:
            response = self._http().get("/api/tags")
            response.raise_for_status()
            names = {item.get("name") for item in response.json().get("models", [])}
            return {
                "provider": self.name,
                "configured": True,
                "reachable": True,
                "model": self.model_name,
                "model_available": self.model_name in names,
                "dimensions": self.dimensions,
            }
        except Exception:
            return {
                "provider": self.name,
                "configured": True,
                "reachable": False,
                "model": self.model_name,
                "model_available": False,
                "dimensions": self.dimensions,
            }
