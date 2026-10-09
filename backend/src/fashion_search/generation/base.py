"""Provider-neutral interfaces for text and structured generation."""

import asyncio
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class GenerationProvider(Protocol):
    """Produce a shopping-assistant reply from a system prompt and messages."""

    name: str
    model_name: str

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        """Return text using provider-neutral inputs."""
        ...

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system_prompt: str | None = None,
    ) -> T:
        """Return content validated against a Pydantic schema."""
        ...

    def health(self) -> dict[str, object]:
        """Return a lightweight configuration/reachability assessment."""
        ...

    async def agenerate(
        self, prompt: str, *, system_prompt: str | None = None
    ) -> str: ...

    async def agenerate_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system_prompt: str | None = None,
    ) -> T: ...


class AsyncGenerationMixin:
    """Non-blocking wrappers for synchronous SDKs used by sync FastAPI routes."""

    async def agenerate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return await asyncio.to_thread(
            self.generate, prompt, system_prompt=system_prompt
        )

    async def agenerate_structured(
        self, prompt: str, schema: type[T], *, system_prompt: str | None = None
    ) -> T:
        return await asyncio.to_thread(
            self.generate_structured, prompt, schema, system_prompt=system_prompt
        )
