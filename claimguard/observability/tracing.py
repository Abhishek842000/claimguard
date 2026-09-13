"""Langfuse span-per-agent wrapper. No-op when keys / host are unset.

Phase 1 will emit real observations; Phase 0 only defines the interface so
agents never talk to Langfuse directly.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from claimguard.observability.pii_redaction import redact_mapping


@contextmanager
def agent_span(name: str, *, claim_id: str, input_payload: Any = None) -> Iterator[dict[str, Any]]:
    """Yield a mutable span dict. Caller sets output / tokens / error."""
    span: dict[str, Any] = {
        "name": name,
        "claim_id": claim_id,
        "input": redact_mapping(input_payload) if input_payload is not None else None,
        "output": None,
        "status": "ok",
    }
    try:
        yield span
    except Exception:
        span["status"] = "error"
        raise
