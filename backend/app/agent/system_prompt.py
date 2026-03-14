from __future__ import annotations

from functools import lru_cache
from pathlib import Path

SYSTEM_PROMPT_PATH = Path(__file__).with_name("prompts") / "system.md"


@lru_cache(maxsize=1)
def build_system_prompt() -> str:
    """Load the project-wide system prompt for TrumanWorld agents."""
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
