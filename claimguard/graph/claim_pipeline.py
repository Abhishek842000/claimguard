"""Claim processing StateGraph.

Topology (this is the backbone — do not linearize the specialists):

    intake_agent
      ├─> vision_agent ─┐
      ├─> fraud_agent  ─┼─> adjudicator_agent ─> route_to_human | auto_resolve
      └─> policy_agent ─┘

Conditional edge after the adjudicator:
    route_to_human  if confidence < threshold OR fraud_score > threshold
                    (also if `error` is set or `verdict` is missing — fail closed)
    auto_resolve    otherwise
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from claimguard.graph.routing import (
    RouteName,
    RoutingThresholds,
    decide_route,
    routing_reason,
)
from claimguard.schemas.common import RoutingDecision
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate


class PipelineNode(StrEnum):
    """Stable graph node names. Used in traces, tests, and the dashboard."""

    INTAKE = "intake_agent"
    VISION = "vision_agent"
    FRAUD = "fraud_agent"
    POLICY = "policy_agent"
    ADJUDICATOR = "adjudicator_agent"
    ROUTE_TO_HUMAN = "route_to_human"
    AUTO_RESOLVE = "auto_resolve"


ClaimNodeFn = Callable[[ClaimState], ClaimStateUpdate]


@dataclass(frozen=True)
class PipelineAgents:
    """Injectable node bodies so tests can compile and invoke without LLM calls."""

    intake_agent: ClaimNodeFn
    vision_agent: ClaimNodeFn
    fraud_agent: ClaimNodeFn
    policy_agent: ClaimNodeFn
    adjudicator_agent: ClaimNodeFn

    @classmethod
    def production(cls) -> PipelineAgents:
        from claimguard.agents.adjudicator_agent import run_adjudicator_agent
        from claimguard.agents.fraud_agent import run_fraud_agent
        from claimguard.agents.intake_agent import run_intake_agent
        from claimguard.agents.policy_agent import run_policy_agent
        from claimguard.agents.vision_agent import run_vision_agent

        return cls(
            intake_agent=run_intake_agent,
            vision_agent=run_vision_agent,
            fraud_agent=run_fraud_agent,
            policy_agent=run_policy_agent,
            adjudicator_agent=run_adjudicator_agent,
        )


def _align_verdict(
    state: ClaimState,
    *,
    requires_human_review: bool,
    reason: str,
) -> ClaimStateUpdate:
    routing = (
        RoutingDecision.HUMAN_REVIEW if requires_human_review else RoutingDecision.AUTO_RESOLVE
    )
    update: ClaimStateUpdate = {"requires_human_review": requires_human_review}
    verdict = state.get("verdict")
    if verdict is None:
        return update
    reasons = list(verdict.routing_reasons)
    if reason not in reasons:
        reasons.append(reason)
    update["verdict"] = verdict.model_copy(
        update={
            "routing": routing,
            "human_review_required": requires_human_review,
            "routing_reasons": reasons,
        }
    )
    return update


def _terminal_node(
    node: PipelineNode,
    *,
    requires_human_review: bool,
    thresholds: RoutingThresholds,
) -> ClaimNodeFn:
    def _run(state: ClaimState) -> ClaimStateUpdate:
        reason = routing_reason(state, thresholds)
        update = _align_verdict(
            state,
            requires_human_review=requires_human_review,
            reason=reason,
        )
        update["trace"] = [
            AgentStep.completed(node.value, metadata={"routing_reason": reason})
        ]
        return update

    return _run


def build_claim_pipeline(
    *,
    agents: PipelineAgents | None = None,
    thresholds: RoutingThresholds | None = None,
) -> CompiledStateGraph:
    """Compile the claim StateGraph.

    Production agents still raise `NotImplementedError` until each specialist
    lands. Pass `agents=` to invoke the topology in tests.
    """

    runners = agents or PipelineAgents.production()
    gates = thresholds or RoutingThresholds.from_settings()

    def route_after_adjudicator(state: ClaimState) -> RouteName:
        return decide_route(state, gates)

    graph = StateGraph(ClaimState)
    graph.add_node(PipelineNode.INTAKE, runners.intake_agent)
    graph.add_node(PipelineNode.VISION, runners.vision_agent)
    graph.add_node(PipelineNode.FRAUD, runners.fraud_agent)
    graph.add_node(PipelineNode.POLICY, runners.policy_agent)
    graph.add_node(PipelineNode.ADJUDICATOR, runners.adjudicator_agent)
    graph.add_node(
        PipelineNode.ROUTE_TO_HUMAN,
        _terminal_node(PipelineNode.ROUTE_TO_HUMAN, requires_human_review=True, thresholds=gates),
    )
    graph.add_node(
        PipelineNode.AUTO_RESOLVE,
        _terminal_node(PipelineNode.AUTO_RESOLVE, requires_human_review=False, thresholds=gates),
    )

    graph.add_edge(START, PipelineNode.INTAKE)
    graph.add_edge(PipelineNode.INTAKE, PipelineNode.VISION)
    graph.add_edge(PipelineNode.INTAKE, PipelineNode.FRAUD)
    graph.add_edge(PipelineNode.INTAKE, PipelineNode.POLICY)
    graph.add_edge(PipelineNode.VISION, PipelineNode.ADJUDICATOR)
    graph.add_edge(PipelineNode.FRAUD, PipelineNode.ADJUDICATOR)
    graph.add_edge(PipelineNode.POLICY, PipelineNode.ADJUDICATOR)
    graph.add_conditional_edges(
        PipelineNode.ADJUDICATOR,
        route_after_adjudicator,
        {
            "route_to_human": PipelineNode.ROUTE_TO_HUMAN,
            "auto_resolve": PipelineNode.AUTO_RESOLVE,
        },
    )
    graph.add_edge(PipelineNode.ROUTE_TO_HUMAN, END)
    graph.add_edge(PipelineNode.AUTO_RESOLVE, END)
    return graph.compile(name="claim_pipeline")
