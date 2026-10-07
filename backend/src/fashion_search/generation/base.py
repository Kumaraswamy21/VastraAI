"""Provider interface for assistant text generation."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GenerationProvider(Protocol):
    """Produce a shopping-assistant reply from a system prompt and messages."""

    name: str

    def generate(self, system_prompt: str, user_message: str) -> str:
        """Return a single completion. Raises on provider failure."""
        ...
