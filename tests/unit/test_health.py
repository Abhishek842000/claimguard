from apps.api.main import create_app
from claimguard.config import Settings
from fastapi.testclient import TestClient


def test_health_returns_200_in_test_env() -> None:
    app = create_app(Settings(app_env="test"))
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "claimguard-api"
    assert body["checks"]["postgres"]["detail"] == "skipped"
    assert body["checks"]["redis"]["detail"] == "skipped"


def test_openapi_advertises_health() -> None:
    app = create_app(Settings(app_env="test"))
    spec = TestClient(app).get("/openapi.json").json()
    assert "/health" in spec["paths"]
    assert spec["info"]["title"] == "ClaimGuard API"
