"""ClaimGuard API process entrypoint."""

from claimguard import __version__
from claimguard.config import Settings, get_settings
from claimguard.logging import configure_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.auth import ApiKeyRateLimitMiddleware, SlidingWindowLimiter
from apps.api.routes import claims, health, metrics


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level, cfg.app_env)

    app = FastAPI(
        title="ClaimGuard API",
        description=(
            "Async insurance-claim triage and fraud detection. "
            "Submit a claim, then poll status / trace / verdict. "
            "The LangGraph pipeline runs in the Celery worker, not on this request path. "
            "Authenticated routes under /v1 require header X-API-Key."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = cfg
    app.state.rate_limiter = SlidingWindowLimiter()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Added last so it is the outermost /v1 gate (Starlette wraps in reverse).
    app.add_middleware(ApiKeyRateLimitMiddleware, limiter=app.state.rate_limiter)
    app.include_router(health.router)
    app.include_router(claims.router)
    app.include_router(metrics.router)
    return app


app = create_app()
