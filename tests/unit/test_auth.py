from apps.api.main import create_app
from claimguard.config import Settings
from fastapi.testclient import TestClient
from pydantic import SecretStr


def _app(**kwargs: object) -> TestClient:
    settings = Settings(app_env="test", api_key=SecretStr("claimguard-local"), **kwargs)
    return TestClient(create_app(settings))


def test_health_is_open_without_api_key() -> None:
    response = _app().get("/health")
    assert response.status_code == 200


def test_v1_rejects_missing_and_wrong_api_key() -> None:
    client = _app()
    missing = client.get("/v1/metrics")
    assert missing.status_code == 401
    wrong = client.get("/v1/metrics", headers={"X-API-Key": "nope"})
    assert wrong.status_code == 401


def test_v1_accepts_configured_api_key(monkeypatch) -> None:
    from decimal import Decimal

    from claimguard.observability.cost_tracker import CostSummary

    monkeypatch.setattr(
        "apps.api.routes.metrics.session_scope",
        __import__("contextlib").contextmanager(lambda: (yield object())),
    )
    monkeypatch.setattr(
        "apps.api.routes.metrics.fetch_cost_metrics",
        lambda session: CostSummary(Decimal("0"), 0, Decimal("0"), []),
    )
    response = _app().get("/v1/metrics", headers={"X-API-Key": "claimguard-local"})
    assert response.status_code == 200


def test_rate_limit_returns_429() -> None:
    client = _app(rate_limit_per_minute=2)
    headers = {"X-API-Key": "claimguard-local"}
    assert client.get("/v1/claims/samples", headers=headers).status_code == 200
    assert client.get("/v1/claims/samples", headers=headers).status_code == 200
    assert client.get("/v1/claims/samples", headers=headers).status_code == 429
