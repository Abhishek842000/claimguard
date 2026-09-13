from decimal import Decimal

from claimguard.observability.cost_tracker import CostTracker, TokenUsage, summarize


def test_cost_tracker_sums_usage() -> None:
    tracker = CostTracker(claim_id="11111111-1111-4111-8111-111111111111")
    tracker.record("intake", "cheap", 120, 80, Decimal("0.0020"))
    tracker.record("fraud", "frontier", 900, 400, Decimal("0.0180"))
    assert tracker.total_cost_usd == Decimal("0.0200")
    assert tracker.total_tokens == 1500


def test_summarize_totals_average_and_agent_breakdown() -> None:
    usages = [
        TokenUsage("intake_agent", "cheap", 100, 40, Decimal("0.0020"), "c1"),
        TokenUsage("fraud_agent", "frontier", 800, 200, Decimal("0.0100"), "c1"),
        TokenUsage("intake_agent", "cheap", 110, 50, Decimal("0.0030"), "c2"),
    ]
    summary = summarize(usages)
    assert summary.claim_count == 2
    assert summary.total_cost_usd == Decimal("0.0150")
    assert summary.average_cost_per_claim == Decimal("0.0075")
    by_agent = {row.agent: row for row in summary.by_agent}
    assert by_agent["intake_agent"].cost_usd == Decimal("0.0050")
    assert by_agent["intake_agent"].steps == 2
    assert by_agent["fraud_agent"].tokens == 1000
