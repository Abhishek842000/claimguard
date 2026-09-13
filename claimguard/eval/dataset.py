"""Load the labeled eval set from data/eval_set/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVAL_SET_DIR = Path(__file__).resolve().parents[2] / "data" / "eval_set"


def load_eval_set(dataset_version: str = "v0") -> list[dict[str, Any]]:
    """Return labeled cases. Missing versions yield an empty list (not an error)."""
    path = EVAL_SET_DIR / f"{dataset_version}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
