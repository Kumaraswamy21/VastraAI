"""LLM generation providers and failover router."""

from fashion_search.generation.base import GenerationProvider

__all__ = ["GenerationProvider", "GenerationRouter"]


def __getattr__(name: str):
    if name == "GenerationRouter":
        from fashion_search.generation.router import GenerationRouter

        return GenerationRouter
    raise AttributeError(name)
