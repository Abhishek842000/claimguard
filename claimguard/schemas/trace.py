"""Observability schemas: per-agent spans, cost, and the full reasoning chain."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from claimguard.schemas.common import AgentName, ClaimGuardModel


class AgentSpan(ClaimGuardModel):
    """One agent (or tool) invocation. Persisted to agent_traces and exported to Langfuse."""

    span_id: str = Field(description="Unique span id (UUIDv4 hex or Langfuse observation id).")
    parent_span_id: str | None = Field(
        default=None,
        description="Parent span, typically the claim-level trace root.",
    )
    agent_name: AgentName = Field(description="Which agent produced this span.")
    started_at: datetime = Field(description="UTC start time.")
    ended_at: datetime | None = Field(
        default=None,
        description="UTC end time. Null while the span is still open.",
    )
    latency_ms: int | None = Field(
        default=None,
        ge=0,
        description="Wall-clock duration in milliseconds.",
    )
    prompt_name: str | None = Field(
        default=None,
        description="Versioned prompt file stem, e.g. 'fraud_v1'.",
    )
    prompt_version: str | None = Field(
        default=None,
        description="Prompt version header, e.g. '1.0.0'.",
    )
    model: str | None = Field(
        default=None,
        description="Model id used for this span, if an LLM was called.",
    )
    input_tokens: int = Field(default=0, ge=0, description="Prompt tokens billed.")
    output_tokens: int = Field(default=0, ge=0, description="Completion tokens billed.")
    cost_usd: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Estimated USD cost for this span.",
    )
    status: Literal["ok", "error", "retry"] = Field(
        description="ok on validated structured output; retry after repair; error after exhaustion.",
    )
    error: str | None = Field(
        default=None,
        description="Redacted error message when status is error or retry.",
    )
    output_schema: str | None = Field(
        default=None,
        description="Pydantic model name of the structured output, e.g. 'FraudSignal'.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-PII extras (chunk ids, retry count). Never store raw claimant fields.",
    )


class AgentTrace(ClaimGuardModel):
    """Full reasoning chain for one claim, shown in the dashboard."""

    claim_id: UUID = Field(description="Claim this trace belongs to.")
    trace_id: str = Field(description="Root trace id, shared with Langfuse.")
    spans: list[AgentSpan] = Field(
        default_factory=list,
        description="Spans in start-time order, including retries.",
    )
    total_cost_usd: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Sum of span costs.",
    )
    total_latency_ms: int = Field(
        default=0,
        ge=0,
        description="End-to-end pipeline wall time, not the sum of span times (agents may run in parallel).",
    )
    routing_path: list[str] = Field(
        default_factory=list,
        description="Ordered graph node names actually visited, e.g. ['intake', 'vision', 'fraud', ...].",
    )
