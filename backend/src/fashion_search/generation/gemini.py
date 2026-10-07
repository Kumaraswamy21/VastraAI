"""Gemini generation provider (primary when quota is available)."""

from fashion_search.generation.base import GenerationProvider


class GeminiGenerator:
    """Google Gemini completions. Satisfies `GenerationProvider`."""

    name = "gemini"

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Call Gemini. Day 4 wires the client and quota handling."""
        raise NotImplementedError("Gemini generation is scheduled for Day 4.")


def build_gemini_generator() -> GenerationProvider:
    """Factory for the primary generation provider."""
    return GeminiGenerator()
