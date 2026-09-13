from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

from apps.api.main import create_app
from claimguard.config import Settings
from fastapi.testclient import TestClient
from pydantic import SecretStr

API_HEADERS = {"X-API-Key": "claimguard-local"}


def _client() -> TestClient:
    return TestClient(create_app(Settings(app_env="test", api_key=SecretStr("claimguard-local"))))


def test_submit_rejects_path_outside_data_root() -> None:
    response = _client().post("/v1/claims", json={"source_dir": "/tmp"}, headers=API_HEADERS)
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
    response = _client().post(
        "/v1/claims",
        json={"source_dir": "data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6"},
        headers=API_HEADERS,
    )
    assert response.status_code == 202
    body = response.json()
    assert body["claim_id"] == str(claim_id)
    assert delayed == [str(claim_id)]


def test_list_claims_returns_status_rows(monkeypatch) -> None:
    @contextmanager
    def fake_scope():
        yield SimpleNamespace()

    monkeypatch.setattr("apps.api.routes.claims.session_scope", fake_scope)
    monkeypatch.setattr(
        "apps.api.routes.claims.list_claims",
        lambda session, limit=50: [
            SimpleNamespace(
                id=UUID("09d919dc-2168-544f-8ec0-4a0f018c8ef6"),
                status="needs_review",
                policy_number="PA-2026-000039",
                incident_type="auto_comprehensive",
                created_at=datetime(2026, 9, 12, tzinfo=UTC),
            )
        ],
    )
    response = _client().get("/v1/claims", headers=API_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body[0]["status"] == "needs_review"
    assert body[0]["policy_number"] == "PA-2026-000039"


def test_upload_claim_writes_files_and_enqueues(monkeypatch, tmp_path) -> None:
    claim_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    delayed: list[str] = []
    dests: list[object] = []

    @contextmanager
    def fake_scope():
        yield SimpleNamespace()

    def fake_create(session, dest, documents, images, notes):
        dests.append((dest, documents, images, notes))
        dest.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(id=claim_id, status="received")

    monkeypatch.setattr("apps.api.routes.claims.session_scope", fake_scope)
    monkeypatch.setattr("apps.api.routes.claims.create_claim_from_uploads", fake_create)
    monkeypatch.setattr("apps.api.routes.claims.process_claim.delay", lambda cid: delayed.append(cid))
    monkeypatch.setattr("apps.api.routes.claims.UPLOADS_ROOT", tmp_path)

    response = _client().post(
        "/v1/claims/upload",
        headers=API_HEADERS,
        data={"notes": "Rear bumper dent after hail."},
        files={"files": ("hail-1.jpg", BytesIO(b"fake-jpeg"), "image/jpeg")},
    )
    assert response.status_code == 202
    assert delayed == [str(claim_id)]
    _dest, documents, images, notes = dests[0]
    assert notes == "Rear bumper dent after hail."
    assert images[0][0] == "hail-1.jpg"
    assert documents == []


def test_list_samples_includes_phoenix_hail() -> None:
    response = _client().get("/v1/claims/samples", headers=API_HEADERS)
    assert response.status_code == 200
    ids = {row["claim_id"] for row in response.json()}
    assert "09d919dc-2168-544f-8ec0-4a0f018c8ef6" in ids
