"""Versioned LLM prompts. A changed prompt gets a new file and version; old ones stay for audit."""

from importlib.resources import files


def load_prompt(name: str) -> str:
    return files(__package__).joinpath(f"{name}.md").read_text(encoding="utf-8").strip()
