from claimguard.config import Settings
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from apps.api.health import check_postgres, check_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """Readiness: 200 only when Postgres and Redis both respond.

    Liveness for orchestrators that need a cheaper probe can treat any
    HTTP response from this process as 'the API is up'; Compose uses this
    endpoint as the container healthcheck.
    """
    settings: Settings = request.app.state.settings
    checks = [check_postgres(settings), check_redis(settings)]
    payload = {
        "status": "ok" if all(c.ok for c in checks) else "unavailable",
        "service": "claimguard-api",
        "checks": {c.name: {"ok": c.ok, "detail": c.detail} for c in checks},
    }
    code = status.HTTP_200_OK if payload["status"] == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=payload)
