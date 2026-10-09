"""Google Gemini hosted embeddings via the google-genai SDK."""

from __future__ import annotations

import random
import time
from typing import Any

from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.embeddings.base import AsyncEmbeddingMixin
from fashion_search.embeddings.base import validate_embedding as _validate_embedding
from fashion_search.embeddings.errors import (
    EmbeddingConfigError,
    EmbeddingTransientError,
    EmbeddingValidationError,
)
from fashion_search.observability.schemas import AIUsage

logger = get_logger(__name__)

TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"


def l2_normalize(vector: Any) -> list[float]:
    """Backward-compatible normalization helper."""
    try:
        values = [float(value) for value in vector]
        return _validate_embedding(values, len(values))
    except Exception as exc:
        raise EmbeddingValidationError(str(exc)) from exc


def validate_embedding(vector: Any, expected_dimensions: int) -> list[float]:
    """Backward-compatible validation raising the legacy error alias."""
    try:
        return _validate_embedding(vector, expected_dimensions)
    except Exception as exc:
        raise EmbeddingValidationError(str(exc)) from exc


class GeminiEmbedder(AsyncEmbeddingMixin):
    """Remote Gemini embeddings. Never downloads model weights."""

    name = "gemini"

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self.model = self._settings.embedding_model
        self.dimensions = self._settings.embedding_dimensions
        self.batch_size = self._settings.embedding_batch_size
        self.max_retries = self._settings.embedding_max_retries
        self._client = client
        self.api_request_count = 0
        self._last_usage = AIUsage()

    def take_usage(self) -> AIUsage:
        usage, self._last_usage = self._last_usage, AIUsage()
        return usage

    @property
    def model_name(self) -> str:
        return self.model

    def _api_key(self) -> str:
        key = (self._settings.gemini_api_key or self._settings.google_api_key).strip()
        if not key:
            raise EmbeddingConfigError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is required for Gemini embeddings"
            )
        return key

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise EmbeddingConfigError(
                "google-genai is not installed; pip install google-genai"
            ) from exc
        self._client = genai.Client(
            api_key=self._api_key(),
            http_options=types.HttpOptions(
                timeout=int(
                    getattr(self._settings, "embedding_timeout_seconds", 30.0) * 1000
                )
            ),
        )
        return self._client

    def embed_text(self, text: str, *, task_type: str = TASK_DOCUMENT) -> list[float]:
        """Embed one string via Gemini."""
        return self.embed_texts([text], task_type=task_type)[0]

    def embed_query(self, query: str) -> list[float]:
        """Embed a natural-language search query with RETRIEVAL_QUERY."""
        return self.embed_text(query, task_type=TASK_QUERY)

    def embed_document(self, text: str) -> list[float]:
        """Embed catalog document text with RETRIEVAL_DOCUMENT."""
        return self.embed_text(text, task_type=TASK_DOCUMENT)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts, task_type=TASK_DOCUMENT)

    def health(self) -> dict[str, object]:
        """Cheap configuration health; no embedding request is made."""
        try:
            self._api_key()
            return {"provider": self.name, "configured": True, "model": self.model}
        except EmbeddingConfigError:
            return {"provider": self.name, "configured": False, "model": self.model}

    def embed_texts(
        self,
        texts: list[str],
        *,
        task_type: str = TASK_DOCUMENT,
    ) -> list[list[float]]:
        """Embed many strings in input order, chunked by batch_size."""
        if not texts:
            return []
        cleaned = [_require_nonempty(text) for text in texts]
        results: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            chunk = cleaned[start : start + self.batch_size]
            results.extend(self._embed_chunk(chunk, task_type=task_type))
        return results

    def _embed_chunk(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        from google.genai import types

        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self.dimensions,
        )
        response = self._call_with_retries(texts, config)
        return self._vectors_from_response(response, expected_count=len(texts))

    def _call_with_retries(self, texts: list[str], config: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self.api_request_count += 1
                logger.info(
                    "gemini_embed_request model=%s count=%s attempt=%s",
                    self.model,
                    len(texts),
                    attempt + 1,
                )
                response = self._get_client().models.embed_content(
                    model=self.model,
                    contents=texts if len(texts) > 1 else texts[0],
                    config=config,
                )
                native = getattr(response, "usage_metadata", None)
                total = getattr(native, "total_token_count", None)
                self._last_usage = AIUsage(total_tokens=total)
                return response
            except EmbeddingConfigError:
                raise
            except Exception as exc:
                if not _is_transient(exc) or attempt >= self.max_retries:
                    if _is_auth_error(exc):
                        raise EmbeddingConfigError(str(exc)) from exc
                    if _is_transient(exc):
                        raise EmbeddingTransientError(str(exc)) from exc
                    raise EmbeddingValidationError(str(exc)) from exc
                last_error = exc
                delay = _backoff_seconds(attempt)
                logger.warning(
                    "gemini_embed_retry attempt=%s delay=%.2fs error=%s",
                    attempt + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)
        raise EmbeddingTransientError(str(last_error))

    def _vectors_from_response(self, response: Any, *, expected_count: int) -> list[list[float]]:
        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            raise EmbeddingValidationError("Gemini response contained no embeddings")
        if len(embeddings) != expected_count:
            raise EmbeddingValidationError(
                f"expected {expected_count} embeddings, got {len(embeddings)}"
            )
        vectors: list[list[float]] = []
        for item in embeddings:
            values = getattr(item, "values", None)
            if values is None and isinstance(item, dict):
                values = item.get("values")
            if values is None:
                raise EmbeddingValidationError("embedding item missing values")
            vectors.append(validate_embedding(list(values), self.dimensions))
        return vectors


def build_gemini_embedder(settings: Settings | None = None) -> GeminiEmbedder:
    """Factory for the Gemini embedding provider."""
    return GeminiEmbedder(settings=settings)


def _require_nonempty(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise EmbeddingValidationError("embedding input text is empty")
    return cleaned


def _backoff_seconds(attempt: int) -> float:
    base = min(32.0, 2**attempt)
    return base + random.uniform(0, 0.5)


def _is_transient(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    markers = (
        "rate",
        "quota",
        "429",
        "503",
        "500",
        "timeout",
        "temporarily",
        "unavailable",
        "connection",
        "reset",
    )
    return any(marker in name or marker in message for marker in markers)


def _is_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("401", "403", "api key", "permission", "unauthenticated"))
