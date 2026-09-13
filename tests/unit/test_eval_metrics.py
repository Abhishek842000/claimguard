from decimal import Decimal

from claimguard.eval.llm_judge import judge_verdict
from claimguard.eval.metrics import compute_metrics


def test_compute_metrics_precision_recall_and_percentiles() -> None:
    rows = [
        {
            "y_true_fraud": True,
            "y_pred_fraud": True,
            "grounded": True,
            "latency_ms": 100,
            "cost_usd": Decimal("0.002"),
        },
        {
            "y_true_fraud": True,
            "y_pred_fraud": False,
            "grounded": False,
            "latency_ms": 200,
            "cost_usd": Decimal("0.004"),
        },
        {
            "y_true_fraud": False,
            "y_pred_fraud": False,
            "grounded": True,
            "latency_ms": 150,
            "cost_usd": Decimal("0.003"),
        },
    ]
    metrics = compute_metrics(rows)
    assert metrics.n_cases == 3
    assert metrics.fraud_precision == 1.0
    assert metrics.fraud_recall == 0.5
    assert metrics.groundedness == 0.6667
    assert metrics.hallucination_rate == 0.3333
    assert metrics.cost_per_claim_usd == Decimal("0.003000")
    assert metrics.latency_p50_ms == 150.0


def test_judge_verdict_drops_ungrounded_citations() -> None:
    scores = judge_verdict(
        {
            "retrieved_ids": ["pap-otc"],
            "cited_ids": ["pap-otc", "pap-invented-99"],
            "has_verdict": True,
            "routing_matches_gates": True,
        }
    )
    assert scores.grounding == 0.5
    assert scores.completeness == 1.0
    assert "judge_v1" in scores.prompt_version
