"""Load versioned prompt YAML from `claimguard/llm/prompts/`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class PromptSpec:
    name: str
    version: str
    tier: str
    schema: str
    system: str
    user: str
    description: str = ""

    def render_user(self, **kwargs: Any) -> str:
        rendered = self.user
        for key, value in kwargs.items():
            rendered = rendered.replace("{{ " + key + " }}", str(value))
        return rendered


def load_prompt(name: str) -> PromptSpec:
    """Load `{name}.yaml`. `name` is the file stem, e.g. 'intake_v1'."""

    path = PROMPTS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PromptSpec(
        name=str(payload["name"]),
        version=str(payload["version"]),
        tier=str(payload.get("tier", "cheap")),
        schema=str(payload["schema"]),
        system=str(payload["system"]).strip(),
        user=str(payload["user"]).strip(),
        description=str(payload.get("description") or "").strip(),
    )
