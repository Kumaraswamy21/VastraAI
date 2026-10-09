"""Single composition boundary for selecting AI providers."""

from __future__ import annotations

from dataclasses import dataclass

from fashion_search.config.settings import Settings, get_settings
from fashion_search.embeddings.base import EmbeddingProvider
from fashion_search.generation.base import GenerationProvider


def get_generation_provider(
    settings: Settings | None = None,
    *,
    provider_name: str | None = None,
    client: object | None = None,
) -> GenerationProvider:
    cfg = settings or get_settings()
    selected = provider_name or getattr(cfg, "generation_provider", "gemini")
    if selected == "gemini":
        from fashion_search.generation.gemini import GeminiGenerator

        provider = GeminiGenerator(cfg, client=client)
        from fashion_search.observability.instrumentation import instrument_generation_provider
        return instrument_generation_provider(provider, cfg)
    if selected == "ollama":
        from fashion_search.generation.ollama import OllamaGemmaGenerator

        provider = OllamaGemmaGenerator(cfg, client=client)
        from fashion_search.observability.instrumentation import instrument_generation_provider
        return instrument_generation_provider(provider, cfg)
    raise ValueError(f"unsupported generation provider: {selected}")


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    cfg = settings or get_settings()
    if cfg.embedding_provider == "gemini":
        from fashion_search.embeddings.gemini import GeminiEmbedder

        provider = GeminiEmbedder(cfg)
        from fashion_search.observability.instrumentation import instrument_embedding_provider
        return instrument_embedding_provider(provider, cfg)
    if cfg.embedding_provider == "ollama":
        from fashion_search.embeddings.ollama import OllamaEmbedder

        provider = OllamaEmbedder(cfg)
        from fashion_search.observability.instrumentation import instrument_embedding_provider
        return instrument_embedding_provider(provider, cfg)
    raise ValueError(f"unsupported embedding provider: {cfg.embedding_provider}")


@dataclass(frozen=True)
class EmbeddingIdentity:
    provider: str
    model: str
    dimensions: int


def get_embedding_identity(settings: Settings | None = None) -> EmbeddingIdentity:
    """Resolve embedding identity without constructing a network client."""
    cfg = settings or get_settings()
    provider = getattr(cfg, "embedding_provider", "gemini")
    if provider == "ollama":
        return EmbeddingIdentity(
            provider="ollama",
            model=cfg.ollama_embedding_model,
            dimensions=cfg.ollama_embedding_dimensions,
        )
    if provider == "gemini":
        return EmbeddingIdentity(
            provider="gemini",
            model=cfg.embedding_model,
            dimensions=cfg.embedding_dimensions,
        )
    raise ValueError(f"unsupported embedding provider: {provider}")


def get_generation_fallback_provider(
    settings: Settings | None = None,
) -> GenerationProvider | None:
    cfg = settings or get_settings()
    if not cfg.generation_fallback_provider:
        return None
    if cfg.generation_fallback_provider == cfg.generation_provider:
        return None
    return get_generation_provider(cfg, provider_name=cfg.generation_fallback_provider)
