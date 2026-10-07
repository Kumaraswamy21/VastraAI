"""Read a named, versioned prompt file from disk."""

from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parent
DEFAULT_VERSION = "v1"


def prompt_path(name: str, version: str = DEFAULT_VERSION) -> Path:
    """Return the path to `prompts/versions/<version>/<name>.md`."""
    return PROMPTS_ROOT / "versions" / version / f"{name}.md"


def load_prompt(name: str, version: str = DEFAULT_VERSION) -> str:
    """Load a prompt file as UTF-8 text.

    `name` is the file stem, for example `system_assistant`.
    """
    path = prompt_path(name, version)
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
