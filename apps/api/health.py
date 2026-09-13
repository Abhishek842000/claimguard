"""Readiness checks used by GET /health and the Compose healthcheck."""

from __future__ import annotations

from dataclasses import dataclass

from claimguard.config import Settings
from claimguard.db.session import get_engine
from redis import Redis
from sqlalchemy import text


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    ok: bool
    detail: str


def check_postgres(settings: Settings) -> DependencyStatus:
    if settings.is_test:
        return DependencyStatus("postgres", True, "skipped")
    try:
        engine = get_engine(settings)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return DependencyStatus("postgres", True, "ok")
    except Exception as exc:
        return DependencyStatus("postgres", False, exc.__class__.__name__)


def check_redis(settings: Settings) -> DependencyStatus:
    if settings.is_test:
        return DependencyStatus("redis", True, "skipped")
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        ok = bool(client.ping())
        client.close()
        return DependencyStatus("redis", ok, "ok" if ok else "ping_failed")
    except Exception as exc:
        return DependencyStatus("redis", False, exc.__class__.__name__)
