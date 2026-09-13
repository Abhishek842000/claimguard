from contextlib import contextmanager
from decimal import Decimal

from apps.api.main import create_app
from claimguard.config import Settings
from claimguard.observability.cost_tracker import AgentCostBreakdown, CostSummary
from fastapi.testclient import TestClient
from pydantic import SecretStr


def test_metrics_returns_aggregation(monkeypatch) -> None:
    @contextmanager
    def fake_scope():
        yield object()

    monkeypatch.setattr("apps.api.routes.metrics.session_scope", fake_scope)
    monkeypatch.setattr(
        "apps.api.routes.metrics.fetch_cost_metrics",
        lambda session: CostSummary(
            total_cost_usd=Decimal("0.0200"),
            claim_count=2,
            average_cost_per_claim=Decimal("0.0100"),
            by_agent=[
                AgentCostBreakdown("intake_agent", Decimal("0.0050"), 300, 2),
                AgentCostBreakdown("fraud_agent", Decimal("0.0150"), 1200, 2),
            ],
        ),
    )
    client = TestClient(
        create_app(Settings(app_env="test", api_key=SecretStr("claimguard-local")))
    )
    response = client.get("/v1/metrics", headers={"X-API-Key": "claimguard-local"})
    assert response.status_code == 200
    body = response.json()
    assert body["claim_count"] == 2
    assert body["total_cost_usd"] == "0.0200"
    assert body["average_cost_per_claim"] == "0.0100"
    assert body["by_agent"][1]["agent"] == "fraud_agent"
