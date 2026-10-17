"""Gemini adapter for provider-neutral generation."""

from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from fashion_search.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderRateLimitError,
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

_GEMINI_JSON_SCHEMA_KEYS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "anyOf",
        "description",
        "enum",
        "items",
        "maxItems",
        "maximum",
        "minItems",
        "minimum",
        "oneOf",
        "prefixItems",
        "properties",
        "required",
        "title",
        "type",
    }
)


def _supported_json_schema(value: Any, *, named_entries: bool = False) -> Any:
    """Keep only Gemini's documented schema keywords; validate locally afterward."""
    if isinstance(value, list):
        return [_supported_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if named_entries:
        return {name: _supported_json_schema(item) for name, item in value.items()}
    return {
        key: _supported_json_schema(item, named_entries=key in {"properties", "$defs"})
        for key, item in value.items()
        if key in _GEMINI_JSON_SCHEMA_KEYS
    }


class GeminiGenerator(AsyncGenerationMixin):
    """Google Gemini completions. Satisfies `GenerationProvider`."""

    name = "gemini"

    def __init__(
        self, settings: Settings | None = None, client: Any | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self.model_name = (
            getattr(self._settings, "generation_model", None)
            or self._settings.search_parser_model
        )
        self._client = client
        self._last_usage = AIUsage()

    def take_usage(self) -> AIUsage:
        usage, self._last_usage = self._last_usage, AIUsage()
        return usage

    def _api_key(self) -> str:
        key = (self._settings.gemini_api_key or self._settings.google_api_key).strip()
        if not key:
            raise AIProviderAuthenticationError("Gemini API key is not configured")
        return key

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self._api_key(),
                http_options=types.HttpOptions(
                    timeout=int(
                        getattr(self._settings, "generation_timeout_seconds", 15.0)
                        * 1000
                    )
                ),
            )
        return self._client

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        from google.genai import types

        sampling = (
            {} if self.model_name.startswith("gemini-3.") else {"temperature": 0.0}
        )
        response = self._call(
            prompt,
            types.GenerateContentConfig(system_instruction=system_prompt, **sampling),
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise AIProviderResponseError("Gemini returned an empty response")
        return text

    def generate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T:
        from google.genai import types

        sampling = (
            {} if self.model_name.startswith("gemini-3.") else {"temperature": 0.0}
        )
        structured_config = (
            {"response_json_schema": _supported_json_schema(schema.model_json_schema())}
            if self.model_name.startswith("gemini-3.")
            else {"response_schema": schema}
        )
        response = self._call(
            prompt,
            types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                **structured_config,
                **sampling,
            ),
        )
        try:
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, schema):
                return parsed
            if parsed is not None:
                return schema.model_validate(parsed)
            return schema.model_validate_json(response.text)
        except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AIProviderResponseError(
                "Gemini returned invalid structured output"
            ) from exc

    def _call(self, prompt: str, config: Any) -> Any:
        max_retries = getattr(
            self._settings,
            "generation_max_retries",
            getattr(self._settings, "search_parser_max_retries", 1),
        )
        for attempt in range(max_retries + 1):
            started = time.perf_counter()
            try:
                response = self._get_client().models.generate_content(
                    model=self.model_name, contents=prompt, config=config
                )
                native = getattr(response, "usage_metadata", None)
                self._last_usage = AIUsage(
                    input_tokens=getattr(native, "prompt_token_count", None),
                    output_tokens=getattr(native, "candidates_token_count", None),
                    total_tokens=getattr(native, "total_token_count", None),
                )
                logger.info(
                    "generation_request provider=%s model=%s latency_ms=%.1f",
                    self.name,
                    self.model_name,
                    (time.perf_counter() - started) * 1000,
                )
                return response
            except AIProviderAuthenticationError:
                raise
            except Exception as exc:
                mapped = _translate(exc)
                api_message = getattr(exc, "message", None)
                if isinstance(api_message, str):
                    api_message = " ".join(api_message.split())[:300]
                logger.warning(
                    "generation_failure provider=%s model=%s mode=%s error_type=%s api_code=%s api_status=%s api_message=%s attempt=%s",
                    self.name,
                    self.model_name,
                    "structured"
                    if getattr(config, "response_mime_type", None)
                    else "text",
                    type(mapped).__name__,
                    getattr(exc, "code", None),
                    getattr(exc, "status", None),
                    api_message,
                    attempt + 1,
                )
                if attempt >= max_retries or not isinstance(
                    mapped,
                    (
                        AIProviderRateLimitError,
                        AIProviderTimeoutError,
                        AIProviderUnavailableError,
                    ),
                ):
                    raise mapped from exc
        raise AIProviderUnavailableError("Gemini generation failed")

    def health(self) -> dict[str, object]:
        try:
            self._api_key()
            return {"provider": self.name, "configured": True, "model": self.model_name}
        except AIProviderAuthenticationError:
            return {
                "provider": self.name,
                "configured": False,
                "model": self.model_name,
            }


def build_gemini_generator(settings: Settings | None = None) -> GenerationProvider:
    """Factory for the primary generation provider."""
    return GeminiGenerator(settings=settings)


def _translate(exc: Exception):
    value = f"{type(exc).__name__} {exc}".lower()
    if any(token in value for token in ("401", "403", "api key", "unauthenticated")):
        return AIProviderAuthenticationError(str(exc))
    if any(token in value for token in ("429", "quota", "rate")):
        return AIProviderRateLimitError(str(exc))
    if "timeout" in value:
        return AIProviderTimeoutError(str(exc))
    if any(token in value for token in ("connection", "500", "503", "unavailable")):
        return AIProviderUnavailableError(str(exc))
    return AIProviderResponseError(str(exc))
