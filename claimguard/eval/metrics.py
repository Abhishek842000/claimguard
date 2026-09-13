"""Deterministic metrics: fraud P/R, groundedness, hallucination, latency, cost."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import quantiles


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
    fraud_tp: int = 0
    fraud_fp: int = 0
    fraud_fn: int = 0
    fraud_tn: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "fraud_precision": self.fraud_precision,
            "fraud_recall": self.fraud_recall,
            "groundedness": self.groundedness,
            "hallucination_rate": self.hallucination_rate,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "cost_per_claim_usd": str(self.cost_per_claim_usd) if self.cost_per_claim_usd is not None else None,
            "n_cases": self.n_cases,
            "fraud_tp": self.fraud_tp,
            "fraud_fp": self.fraud_fp,
            "fraud_fn": self.fraud_fn,
            "fraud_tn": self.fraud_tn,
        }


def compute_metrics(rows: list[dict[str, object]]) -> EvalMetrics:
    """Aggregate one eval pass. Missing keys are treated as unknown, not as zeros."""
    tp = fp = fn = tn = 0
    grounded_flags: list[bool] = []
    latencies: list[float] = []
    costs: list[Decimal] = []
    for row in rows:
        truth = row.get("y_true_fraud")
        pred = row.get("y_pred_fraud")
        if isinstance(truth, bool) and isinstance(pred, bool):
            if truth and pred:
                tp += 1
            elif pred and not truth:
                fp += 1
            elif truth and not pred:
                fn += 1
            else:
                tn += 1
        if isinstance(row.get("grounded"), bool):
            grounded_flags.append(bool(row["grounded"]))
        latency = row.get("latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
        cost = row.get("cost_usd")
        if isinstance(cost, Decimal):
            costs.append(cost)
        elif isinstance(cost, (int, float, str)):
            costs.append(Decimal(str(cost)))
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    groundedness = (sum(grounded_flags) / len(grounded_flags)) if grounded_flags else None
    hallucination = (1.0 - groundedness) if groundedness is not None else None
    return EvalMetrics(
        fraud_precision=_round(precision),
        fraud_recall=_round(recall),
        groundedness=_round(groundedness),
        hallucination_rate=_round(hallucination),
        latency_p50_ms=_percentile(latencies, 50),
        latency_p95_ms=_percentile(latencies, 95),
        cost_per_claim_usd=(sum(costs, Decimal("0")) / len(costs)).quantize(Decimal("0.000001"))
        if costs
        else None,
        n_cases=len(rows),
        fraud_tp=tp,
        fraud_fp=fp,
        fraud_fn=fn,
        fraud_tn=tn,
    )


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _percentile(values: list[float], pct: int) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 1)
    pts = quantiles(values, n=100, method="inclusive")
    return round(pts[pct - 1], 1)
