"""Ollama Gemma generation provider (local fallback)."""

from fashion_search.generation.base import GenerationProvider


class OllamaGemmaGenerator:
    """Local Gemma via Ollama. Satisfies `GenerationProvider`."""

    name = "ollama_gemma"

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Call Ollama. Day 4 wires the HTTP client."""
        raise NotImplementedError("Ollama generation is scheduled for Day 4.")


def build_ollama_generator() -> GenerationProvider:
    """Factory for the local fallback generation provider."""
    return OllamaGemmaGenerator()
