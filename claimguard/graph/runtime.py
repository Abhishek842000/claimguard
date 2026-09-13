"""Invoke the compiled graph with per-node error capture and Langfuse export."""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal

from claimguard.graph.claim_pipeline import PipelineAgents, build_claim_pipeline
from claimguard.graph.routing import RoutingThresholds
from claimguard.observability.langfuse import LangfuseSink, NullSink
from claimguard.observability.pii_redaction import redact_mapping, redact_pii
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate

ClaimNodeFn = Callable[[ClaimState], ClaimStateUpdate]


def invoke_claim_pipeline(
    state: ClaimState,
    *,
    agents: PipelineAgents | None = None,
    thresholds: RoutingThresholds | None = None,
    sink: LangfuseSink | NullSink | None = None,
) -> ClaimState:
    tracer: LangfuseSink | NullSink = sink if sink is not None else LangfuseSink()
    tracer.add_trace(claim_id=state["claim_id"])
    graph = build_claim_pipeline(
        agents=_guarded(agents or PipelineAgents.production()),
        thresholds=thresholds,
    )
    result: ClaimState = graph.invoke(state)
    for step in result.get("trace") or []:
        tracer.add_span(step, claim_id=state["claim_id"])
    tracer.flush()
    return result


def _guarded(agents: PipelineAgents) -> PipelineAgents:
    return PipelineAgents(
        intake_agent=_guard("intake_agent", agents.intake_agent),
        vision_agent=_guard("vision_agent", agents.vision_agent),
        fraud_agent=_guard("fraud_agent", agents.fraud_agent),
        policy_agent=_guard("policy_agent", agents.policy_agent),
        adjudicator_agent=_guard("adjudicator_agent", agents.adjudicator_agent),
    )


def _guard(name: str, fn: ClaimNodeFn) -> ClaimNodeFn:
    def node(state: ClaimState) -> ClaimStateUpdate:
        started = time.perf_counter()
        input_snapshot = redact_mapping(_input_snapshot(name, state))
        try:
            update = fn(state)
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            error = redact_pii(f"{name} failed: {type(exc).__name__}: {exc}")
            return {
                "error": error,
                "requires_human_review": True,
                "trace": [
                    AgentStep.completed(
                        name,
                        status="error",
                        error=error,
                        latency_ms=latency,
                        input_snapshot=input_snapshot,
                    )
                ],
            }
        latency = int((time.perf_counter() - started) * 1000)
        steps = list(update.get("trace") or [])
        if not steps:
            steps = [AgentStep.completed(name, latency_ms=latency, input_snapshot=input_snapshot)]
        enriched: list[AgentStep] = []
        for step in steps:
            tokens_in = step.input_tokens or max(1, len(str(input_snapshot)) // 4)
            tokens_out = step.output_tokens or max(1, len(str(step.output_snapshot)) // 4)
            cost = step.cost_usd or Decimal(tokens_in * 15 + tokens_out * 60) / Decimal("100000000")
            enriched.append(
                step.model_copy(
                    update={
                        "latency_ms": step.latency_ms or latency,
                        "input_snapshot": step.input_snapshot or input_snapshot,
                        "output_snapshot": redact_mapping(step.output_snapshot),
                        "input_tokens": tokens_in,
                        "output_tokens": tokens_out,
                        "cost_usd": cost,
                    }
                )
            )
        update["trace"] = enriched
        return update

    return node


def _input_snapshot(name: str, state: ClaimState) -> dict[str, object]:
    if name == "intake_agent":
        return {
            "claim_id": state["claim_id"],
            "document_count": len(state.get("raw_documents") or []),
            "image_count": len(state.get("raw_images") or []),
        }
    intake = state.get("intake")
    return {
        "claim_id": state["claim_id"],
        "has_intake": intake is not None,
        "has_damage": state.get("damage_assessment") is not None,
        "has_fraud": state.get("fraud_signal") is not None,
        "has_policy": state.get("policy_determination") is not None,
    }
