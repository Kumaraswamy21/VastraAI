"""Load versioned prompt files. System prompts are never hardcoded in Python."""

from fashion_search.prompts.loader import load_prompt

__all__ = ["load_prompt"]
