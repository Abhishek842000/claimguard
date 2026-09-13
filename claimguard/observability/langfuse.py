"""Real Langfuse export via the public ingestion API.

Uses HTTP (not a stub). If Langfuse is down, the claim still completes — we
record the failure on the sink so ops can see a dropped trace without failing
triage. Host/keys come from Settings (self-hosted on :3000 locally).
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import structlog

from claimguard.config import Settings, get_settings
from claimguard.observability.pii_redaction import redact_mapping
from claimguard.schemas.graph import AgentStep

log = structlog.get_logger("claimguard.langfuse")


class LangfuseSink:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.events: list[dict[str, Any]] = []
        self.trace_id = uuid4().hex
        self.errors: list[str] = []

    def add_trace(self, *, claim_id: str, name: str = "claim_pipeline") -> None:
        now = _iso()
        self.events.append(
            {
                "id": uuid4().hex,
                "timestamp": now,
                "type": "trace-create",
                "body": {
                    "id": self.trace_id,
                    "name": name,
                    "timestamp": now,
                    "metadata": {"claim_id": claim_id},
                    "tags": ["claimguard", "langgraph"],
                },
            }
        )

    def add_span(self, step: AgentStep, *, claim_id: str) -> None:
        now = _iso()
        body: dict[str, Any] = {
            "id": uuid4().hex,
            "traceId": self.trace_id,
            "name": step.agent,
            "startTime": step.started_at.isoformat(),
            "endTime": (step.ended_at or step.started_at).isoformat(),
            "input": redact_mapping(step.input_snapshot),
            "output": redact_mapping(step.output_snapshot),
            "metadata": {
                "claim_id": claim_id,
                "prompt_version": step.prompt_version,
                "model": step.model,
                "status": step.status,
                **{key: value for key, value in step.metadata.items() if key != "claimant"},
            },
            "level": "ERROR" if step.status == "error" else "DEFAULT",
            "statusMessage": step.error,
        }
        self.events.append(
            {"id": uuid4().hex, "timestamp": now, "type": "span-create", "body": body}
        )
        if step.model or step.input_tokens or step.output_tokens:
            self.events.append(
                {
                    "id": uuid4().hex,
                    "timestamp": now,
                    "type": "generation-create",
                    "body": {
                        "id": uuid4().hex,
                        "traceId": self.trace_id,
                        "name": f"{step.agent}:generation",
                        "startTime": step.started_at.isoformat(),
                        "endTime": (step.ended_at or step.started_at).isoformat(),
                        "model": step.model or "unknown",
                        "input": redact_mapping(step.input_snapshot),
                        "output": redact_mapping(step.output_snapshot),
                        "usage": {
                            "input": step.input_tokens,
                            "output": step.output_tokens,
                            "total": step.input_tokens + step.output_tokens,
                            "unit": "TOKENS",
                        },
                        "metadata": {
                            "prompt_version": step.prompt_version,
                            "cost_usd": str(step.cost_usd),
                        },
                    },
                }
            )

    def flush(self) -> None:
        if not self.events:
            return
        host = self.settings.langfuse_host.rstrip("/")
        public = self.settings.langfuse_public_key
        secret = self.settings.langfuse_secret_key.get_secret_value()
        token = base64.b64encode(f"{public}:{secret}".encode()).decode()
        try:
            response = httpx.post(
                f"{host}/api/public/ingestion",
                headers={
                    "Authorization": f"Basic {token}",
                    "Content-Type": "application/json",
                },
                json={"batch": self.events},
                timeout=8.0,
            )
            if response.status_code >= 400:
                self.errors.append(f"{response.status_code}: {response.text[:300]}")
                log.warning("langfuse_ingest_failed", status=response.status_code)
            else:
                log.info("langfuse_ingest_ok", events=len(self.events), trace_id=self.trace_id)
        except Exception as exc:
            self.errors.append(exc.__class__.__name__)
            log.warning("langfuse_ingest_error", error=exc.__class__.__name__)
        finally:
            self.events.clear()


class NullSink:
    trace_id = "local"

    def __init__(self) -> None:
        self.errors: list[str] = []

    def add_trace(self, *, claim_id: str, name: str = "claim_pipeline") -> None:
        return None

    def add_span(self, step: AgentStep, *, claim_id: str) -> None:
        return None

    def flush(self) -> None:
        return None


def _iso() -> str:
    return datetime.now(UTC).isoformat()
