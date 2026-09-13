"""API-key gate and an in-process sliding-window rate limiter.

Choice: one shared key + in-memory limiter (not Redis, not JWT). Enough to
show the API is not anonymously writable; a real deploy would swap this for
an IdP and a distributed counter. The limiter is per API process — Compose
runs a single API replica locally.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from claimguard.config import Settings
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_s:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


class ApiKeyRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limiter: SlidingWindowLimiter) -> None:
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS" or not request.url.path.startswith("/v1"):
            return await call_next(request)
        settings: Settings = request.app.state.settings
        presented = _presented_key(request)
        expected = settings.api_key.get_secret_value()
        if not presented or presented != expected:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
            )
        # GETs are dashboard polls (list/metrics/detail). Counting them in the
        # same window as POST /upload made a tab left open for a minute block
        # the demo. Key still required on GET; only writes share the tight cap.
        if request.method in _WRITE_METHODS:
            if not self.limiter.allow(presented, settings.rate_limit_per_minute):
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": "60"},
                    content={
                        "detail": (
                            "Rate limit exceeded. Wait 60 seconds, or raise "
                            "RATE_LIMIT_PER_MINUTE. List/metrics polls do not count."
                        ),
                    },
                )
        return await call_next(request)


def _presented_key(request: Request) -> str:
    header = request.headers.get("x-api-key")
    if header:
        return header.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""
