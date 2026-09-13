"""Load or generate the labeled eval set from data/eval_set/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

EVAL_SET_DIR = Path(__file__).resolve().parents[2] / "data" / "eval_set"


def load_eval_set(dataset_version: str = "v0") -> list[dict[str, Any]]:
    """Return labeled cases. Phase 4 fills this from JSONL produced by seed_eval_set."""
    path = EVAL_SET_DIR / f"{dataset_version}.jsonl"
    if not path.exists():
        return []
    raise NotImplementedError("JSONL loader is implemented in Phase 4")
