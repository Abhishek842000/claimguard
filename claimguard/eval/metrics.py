"""Deterministic metrics: fraud P/R, groundedness, hallucination, latency, cost."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EvalMetrics:
    fraud_precision: float | None
    fraud_recall: float | None
    groundedness: float | None
    hallucination_rate: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    cost_per_claim_usd: Decimal | None
    n_cases: int


def compute_metrics(_rows: list[dict[object, object]]) -> EvalMetrics:
    raise NotImplementedError("Metric aggregation is implemented in Phase 4")
