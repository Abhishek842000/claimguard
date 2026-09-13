"""Lightweight integration-shaped tests that do not require Docker.

Full Compose /health against live Postgres + Redis is verified in Phase 0
acceptance by `docker compose up` + curl, not by this module.
"""

from apps.api.main import create_app
from claimguard.config import Settings
from fastapi.testclient import TestClient


def test_claims_routes_are_registered() -> None:
    client = TestClient(create_app(Settings(app_env="test")))
    response = client.post("/v1/claims")
    assert response.status_code == 422
