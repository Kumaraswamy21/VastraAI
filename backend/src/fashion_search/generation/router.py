"""Configured generation provider with optional provider-neutral fallback."""

from typing import TypeVar

from pydantic import BaseModel

from fashion_search.ai.errors import AIProviderError
from fashion_search.ai.factory import (
    get_generation_fallback_provider,
    get_generation_provider,
)
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.logging import get_logger
from fashion_search.generation.base import AsyncGenerationMixin, GenerationProvider

T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class GenerationRouter(AsyncGenerationMixin):
    """Try the primary provider, then the local fallback.

    Day 4 will catch quota and network errors from Gemini and retry Gemma.
    """

    def __init__(
        self,
        primary: GenerationProvider | None = None,
        fallback: GenerationProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._primary = primary or get_generation_provider(cfg)
        self._fallback = fallback or get_generation_fallback_provider(cfg)

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return self._run("generate", prompt, system_prompt=system_prompt)

    def generate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T:
        return self._run(
            "generate_structured", prompt, schema, system_prompt=system_prompt
        )

    def _run(self, method: str, *args, **kwargs):
        try:
            return getattr(self._primary, method)(*args, **kwargs)
        except AIProviderError:
            if self._fallback is None:
                raise
            logger.warning(
                "generation_fallback primary=%s fallback=%s",
                self._primary.name, self._fallback.name,
            )
            return getattr(self._fallback, method)(*args, **kwargs)

    @property
    def name(self) -> str:
        return self._primary.name

    @property
    def model_name(self) -> str:
        return self._primary.model_name

    def health(self) -> dict[str, object]:
        return self._primary.health()
