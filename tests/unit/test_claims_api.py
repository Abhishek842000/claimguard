from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

from apps.api.main import create_app
from claimguard.config import Settings
from fastapi.testclient import TestClient


def test_submit_rejects_path_outside_data_root() -> None:
    client = TestClient(create_app(Settings(app_env="test")))
    response = client.post("/v1/claims", json={"source_dir": "/tmp"})
    assert response.status_code == 400


def test_submit_enqueues_process_claim(monkeypatch) -> None:
    claim_id = UUID("09d919dc-2168-544f-8ec0-4a0f018c8ef6")
    delayed: list[str] = []

    @contextmanager
    def fake_scope():
        yield SimpleNamespace()

    monkeypatch.setattr("apps.api.routes.claims.session_scope", fake_scope)
    monkeypatch.setattr(
        "apps.api.routes.claims.create_claim_from_source_dir",
        lambda session, source: SimpleNamespace(id=claim_id, status="received"),
    )
    monkeypatch.setattr(
        "apps.api.routes.claims.process_claim.delay",
        lambda cid: delayed.append(cid),
    )
    client = TestClient(create_app(Settings(app_env="test")))
    response = client.post(
        "/v1/claims",
        json={"source_dir": "data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["claim_id"] == str(claim_id)
    assert delayed == [str(claim_id)]
