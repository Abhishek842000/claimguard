from decimal import Decimal

from claimguard.observability.cost_tracker import CostTracker


def test_cost_tracker_sums_usage() -> None:
    tracker = CostTracker(claim_id="11111111-1111-4111-8111-111111111111")
    tracker.record("intake", "cheap", 120, 80, Decimal("0.0020"))
    tracker.record("fraud", "frontier", 900, 400, Decimal("0.0180"))
    assert tracker.total_cost_usd == Decimal("0.0200")
    assert tracker.total_tokens == 1500
