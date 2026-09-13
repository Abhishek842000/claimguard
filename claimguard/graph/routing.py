"""Deterministic post-adjudicator routing. The LLM proposes; the graph decides."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from claimguard.config import get_settings
from claimguard.schemas.graph import ClaimState

RouteName = Literal["route_to_human", "auto_resolve"]


@dataclass(frozen=True)
class RoutingThresholds:
    """Hard gates on the adjudicator → {human, auto} conditional edge.

    Route to a human if `confidence < confidence` OR `fraud_score > fraud_score`.
    Defaults match `adjudicator_v1.yaml` (0.65 / 0.45).
    """

    confidence: float = 0.65
    fraud_score: float = 0.45

    @classmethod
    def from_settings(cls) -> RoutingThresholds:
        settings = get_settings()
        return cls(
            confidence=settings.routing_confidence_threshold,
            fraud_score=settings.routing_fraud_score_threshold,
        )


def decide_route(
    state: ClaimState,
    thresholds: RoutingThresholds | None = None,
) -> RouteName:
    """Conditional-edge path function.

    Fail closed (human review) when the run errored or the adjudicator produced
    no verdict. Otherwise apply the two numeric gates from the pipeline spec.
    """

    gates = thresholds or RoutingThresholds.from_settings()
    if state.get("error"):
        return "route_to_human"

    verdict = state.get("verdict")
    if verdict is None:
        return "route_to_human"

    confidence = verdict.overall_confidence
    fraud_score = verdict.fraud_risk_score
    signal = state.get("fraud_signal")
    if signal is not None:
        fraud_score = max(fraud_score, signal.fraud_risk_score)

    if confidence < gates.confidence:
        return "route_to_human"
    if fraud_score > gates.fraud_score:
        return "route_to_human"
    return "auto_resolve"


def routing_reason(state: ClaimState, thresholds: RoutingThresholds) -> str:
    """Human-readable why for the terminal node's verdict alignment."""

    if state.get("error"):
        return f"graph: error present ({state['error']})"
    verdict = state.get("verdict")
    if verdict is None:
        return "graph: missing verdict"
    if verdict.overall_confidence < thresholds.confidence:
        return (
            f"graph: confidence {verdict.overall_confidence:.2f} "
            f"< {thresholds.confidence:.2f}"
        )
    fraud_score = verdict.fraud_risk_score
    signal = state.get("fraud_signal")
    if signal is not None:
        fraud_score = max(fraud_score, signal.fraud_risk_score)
    if fraud_score > thresholds.fraud_score:
        return f"graph: fraud_score {fraud_score:.2f} > {thresholds.fraud_score:.2f}"
    return "graph: auto_resolve thresholds cleared"
