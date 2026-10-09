"""Ollama HTTP adapter for provider-neutral generation."""

from __future__ import annotations

import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from fashion_search.ai.errors import (
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.generation.base import AsyncGenerationMixin, GenerationProvider
from fashion_search.observability.schemas import AIUsage

T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class OllamaGemmaGenerator(AsyncGenerationMixin):
    """Local Gemma via Ollama. Satisfies `GenerationProvider`."""

    name = "ollama"

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self.model_name = self._settings.ollama_generation_model
        self._client = client
        self._last_usage = AIUsage()

    def take_usage(self) -> AIUsage:
        usage, self._last_usage = self._last_usage, AIUsage()
        return usage

    def _http(self):
        return self._client or httpx.Client(
            base_url=self._settings.ollama_base_url,
            timeout=self._settings.ollama_timeout_seconds,
        )

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        payload = {"model": self.model_name, "prompt": prompt, "stream": False}
        if system_prompt:
            payload["system"] = system_prompt
        data = self._post("/api/generate", payload)
        text = str(data.get("response", "")).strip()
        if not text:
            raise AIProviderResponseError("Ollama returned an empty response")
        return text

    def generate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": schema.model_json_schema(),
        }
        if system_prompt:
            payload["system"] = system_prompt
        data = self._post("/api/generate", payload)
        try:
            return schema.model_validate_json(data.get("response", ""))
        except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AIProviderResponseError("Ollama returned invalid structured output") from exc

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = self._http().post(path, json=payload)
            response.raise_for_status()
            data = response.json()
            input_tokens = data.get("prompt_eval_count")
            output_tokens = data.get("eval_count")
            self._last_usage = AIUsage(
                input_tokens=input_tokens if isinstance(input_tokens, int) else None,
                output_tokens=output_tokens if isinstance(output_tokens, int) else None,
                total_tokens=(input_tokens + output_tokens) if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None,
            )
            logger.info(
                "generation_request provider=%s model=%s latency_ms=%.1f",
                self.name, self.model_name, (time.perf_counter() - started) * 1000,
            )
            return data
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError("Ollama request timed out") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise AIProviderUnavailableError("Ollama is unavailable") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise AIProviderUnavailableError("Ollama model is unavailable") from exc
            raise AIProviderResponseError(f"Ollama HTTP {exc.response.status_code}") from exc
        except (ValueError, TypeError) as exc:
            raise AIProviderResponseError("Ollama returned invalid JSON") from exc

    def health(self) -> dict[str, object]:
        try:
            response = self._http().get("/api/tags")
            response.raise_for_status()
            names = {item.get("name") for item in response.json().get("models", [])}
            return {
                "provider": self.name, "configured": True,
                "reachable": True, "model": self.model_name,
                "model_available": self.model_name in names,
            }
        except Exception:
            return {
                "provider": self.name, "configured": True,
                "reachable": False, "model": self.model_name,
                "model_available": False,
            }


def build_ollama_generator(settings: Settings | None = None) -> GenerationProvider:
    """Factory for the local fallback generation provider."""
    return OllamaGemmaGenerator(settings=settings)
