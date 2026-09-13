"""Runtime configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings. Safe to instantiate in API, worker, and CLI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_env: str = Field(default="local", description="local | test | staging | prod")
    log_level: str = Field(default="info")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    database_url: str = Field(
        default="postgresql+psycopg://claimguard:claimguard@localhost:5434/claimguard",
        description="SQLAlchemy URL for the ClaimGuard Postgres/pgvector database.",
    )
    redis_url: str = Field(
        default="redis://:claimguard-redis@localhost:6379/0",
        description="Redis URL used for liveness checks and light caching.",
    )
    celery_broker_url: str = Field(
        default="redis://:claimguard-redis@localhost:6379/1",
    )
    celery_result_backend: str = Field(
        default="redis://:claimguard-redis@localhost:6379/1",
    )

    embedding_dim: int = Field(
        default=768,
        description="Must match the pgvector column width and BAAI/bge-base-en-v1.5.",
    )
    embedding_model: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="FastEmbed / HF model id used by ingest and query scripts.",
    )

    cheap_model: str = Field(default="openai/gpt-4o-mini")
    frontier_model: str = Field(default="openai/gpt-4o")
    openai_api_key: SecretStr | None = Field(default=None)

    langfuse_host: str = Field(default="http://localhost:3000")
    langfuse_public_key: str = Field(default="pk-lf-claimguard-local")
    langfuse_secret_key: SecretStr = Field(default=SecretStr("sk-lf-claimguard-local"))

    # Shared-secret stub, not OAuth. Signals "this API is not a wide-open LAN
    # toy" without adding a full IdP. Rotate via CLAIMGUARD_API_KEY in .env.
    api_key: SecretStr = Field(
        default=SecretStr("claimguard-local"),
        validation_alias=AliasChoices("claimguard_api_key", "api_key"),
        description="Shared secret for /v1. Send as header X-API-Key.",
    )
    rate_limit_per_minute: int = Field(
        default=120,
        ge=0,
        description="Sliding-window cap per API key on POST/PUT/PATCH/DELETE. GETs are polls and do not count. 0 disables the limiter.",
    )

    routing_confidence_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Route to a human when verdict.overall_confidence is below this value.",
    )
    routing_fraud_score_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Route to a human when fraud_risk_score is above this value.",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _psycopg_driver(cls, value: object) -> object:
        """Fly / Railway attach `postgres://`; SQLAlchemy needs the psycopg driver."""
        if not isinstance(value, str):
            return value
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix) and "+psycopg" not in value:
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def override_settings(**kwargs: object) -> Settings:
    """Replace the cached settings object. Used by tests."""
    get_settings.cache_clear()
    settings = Settings(**kwargs)
    get_settings.cache_clear()

    @lru_cache
    def _cached() -> Settings:
        return settings

    # Not swapping the function globally — tests should pass settings explicitly
    # or set APP_ENV=test. This helper exists for future FastAPI overrides.
    return settings
