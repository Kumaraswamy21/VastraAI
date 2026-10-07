"""Choose Gemini first, then Ollama Gemma if Gemini is unavailable."""

from fashion_search.generation.base import GenerationProvider
from fashion_search.generation.gemini import build_gemini_generator
from fashion_search.generation.ollama import build_ollama_generator


class GenerationRouter:
    """Try the primary provider, then the local fallback.

    Day 4 will catch quota and network errors from Gemini and retry Gemma.
    """

    def __init__(
        self,
        primary: GenerationProvider | None = None,
        fallback: GenerationProvider | None = None,
    ) -> None:
        self._primary = primary or build_gemini_generator()
        self._fallback = fallback or build_ollama_generator()

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Return a completion from Gemini or, on failure, Gemma."""
        raise NotImplementedError(
            "Generation failover is scheduled for Day 4 "
            f"(primary={self._primary.name}, fallback={self._fallback.name})."
        )
