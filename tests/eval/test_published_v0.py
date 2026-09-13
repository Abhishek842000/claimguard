"""README and resume bullets must cite the checked-in v0 harness artifact."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_readme_and_resume_match_published_v0_artifact() -> None:
    report = json.loads((REPO / "eval_runs" / "v0.json").read_text(encoding="utf-8"))
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    bullets = (REPO / "RESUME_BULLETS.md").read_text(encoding="utf-8")
    before = report["before"]
    after = report["after"]
    assert report["n_cases"] == 18
    assert after["fraud_fp"] == 0
    for document in (readme, bullets):
        assert str(before["fraud_precision"]) in document
        assert str(after["fraud_precision"]) in document
        assert str(after["fraud_recall"]) in document
        assert str(after["groundedness"]) in document
        assert str(after["hallucination_rate"]) in document
        assert str(after["cost_per_claim_usd"]) in document
        assert f"{after['latency_p50_ms']}" in document
        assert f"{after['latency_p95_ms']}" in document
