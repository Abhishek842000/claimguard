"""Compile and invoke the claim StateGraph with stub specialists."""

from __future__ import annotations

from claimguard.graph import PipelineAgents, PipelineNode, build_claim_pipeline, decide_route
from claimguard.graph.routing import RoutingThresholds
from claimguard.schemas.common import RoutingDecision
from claimguard.schemas.damage import DamageAssessment
from claimguard.schemas.fraud import FraudSignal
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate, empty_claim_state
from claimguard.schemas.intake import ClaimIntake
from claimguard.schemas.policy import PolicyDetermination
from claimguard.schemas.verdict import TriageVerdict


def _step(agent: str, output_schema: str | None = None) -> list[AgentStep]:
    return [AgentStep.completed(agent, output_schema=output_schema)]


def _stub_agents(mocked_llm_responses: dict[str, object]) -> PipelineAgents:
    intake: ClaimIntake = mocked_llm_responses["intake"]  # type: ignore[assignment]
    damage: DamageAssessment = mocked_llm_responses["damage"]  # type: ignore[assignment]
    fraud: FraudSignal = mocked_llm_responses["fraud"]  # type: ignore[assignment]
    policy: PolicyDetermination = mocked_llm_responses["policy"]  # type: ignore[assignment]
    verdict: TriageVerdict = mocked_llm_responses["verdict"]  # type: ignore[assignment]

    def intake_agent(state: ClaimState) -> ClaimStateUpdate:
        return {"intake": intake, "trace": _step(PipelineNode.INTAKE, "ClaimIntake")}

    def vision_agent(state: ClaimState) -> ClaimStateUpdate:
        assert state["intake"] is not None
        return {
            "damage_assessment": damage,
            "trace": _step(PipelineNode.VISION, "DamageAssessment"),
        }

    def fraud_agent(state: ClaimState) -> ClaimStateUpdate:
        assert state["intake"] is not None
        return {"fraud_signal": fraud, "trace": _step(PipelineNode.FRAUD, "FraudSignal")}

    def policy_agent(state: ClaimState) -> ClaimStateUpdate:
        assert state["intake"] is not None
        return {
            "policy_determination": policy,
            "trace": _step(PipelineNode.POLICY, "PolicyDetermination"),
        }

    def adjudicator_agent(state: ClaimState) -> ClaimStateUpdate:
        assert state["damage_assessment"] is not None
        assert state["fraud_signal"] is not None
        assert state["policy_determination"] is not None
        return {"verdict": verdict, "trace": _step(PipelineNode.ADJUDICATOR, "TriageVerdict")}

    return PipelineAgents(
        intake_agent=intake_agent,
        vision_agent=vision_agent,
        fraud_agent=fraud_agent,
        policy_agent=policy_agent,
        adjudicator_agent=adjudicator_agent,
    )


def _auto_verdict(verdict: TriageVerdict) -> TriageVerdict:
    return verdict.model_copy(
        update={
            "overall_confidence": 0.80,
            "fraud_risk_score": 0.10,
            "routing": RoutingDecision.AUTO_RESOLVE,
            "human_review_required": False,
            "routing_reasons": [],
        }
    )


def test_pipeline_topology_fans_out_then_routes() -> None:
    compiled = build_claim_pipeline()
    edges = {(edge.source, edge.target) for edge in compiled.get_graph().edges}
    expected = {
        ("__start__", PipelineNode.INTAKE.value),
        (PipelineNode.INTAKE.value, PipelineNode.VISION.value),
        (PipelineNode.INTAKE.value, PipelineNode.FRAUD.value),
        (PipelineNode.INTAKE.value, PipelineNode.POLICY.value),
        (PipelineNode.VISION.value, PipelineNode.ADJUDICATOR.value),
        (PipelineNode.FRAUD.value, PipelineNode.ADJUDICATOR.value),
        (PipelineNode.POLICY.value, PipelineNode.ADJUDICATOR.value),
        (PipelineNode.ADJUDICATOR.value, PipelineNode.ROUTE_TO_HUMAN.value),
        (PipelineNode.ADJUDICATOR.value, PipelineNode.AUTO_RESOLVE.value),
        (PipelineNode.ROUTE_TO_HUMAN.value, "__end__"),
        (PipelineNode.AUTO_RESOLVE.value, "__end__"),
    }
    assert expected <= edges


def test_invoke_auto_resolves_when_thresholds_clear(
    mocked_llm_responses: dict[str, object],
) -> None:
    responses = dict(mocked_llm_responses)
    responses["verdict"] = _auto_verdict(mocked_llm_responses["verdict"])  # type: ignore[arg-type]
    # keep fraud_signal low so max(verdict, signal) still clears
    fraud: FraudSignal = responses["fraud"]  # type: ignore[assignment]
    responses["fraud"] = fraud.model_copy(update={"fraud_risk_score": 0.10})

    compiled = build_claim_pipeline(agents=_stub_agents(responses))
    claim: ClaimIntake = responses["intake"]  # type: ignore[assignment]
    result = compiled.invoke(empty_claim_state(str(claim.claim_id)))

    assert result["intake"] is not None
    assert result["damage_assessment"] is not None
    assert result["fraud_signal"] is not None
    assert result["policy_determination"] is not None
    assert result["verdict"] is not None
    assert result["requires_human_review"] is False
    assert result["verdict"].routing == RoutingDecision.AUTO_RESOLVE
    agents = [step.agent for step in result["trace"]]
    assert agents[0] == PipelineNode.INTAKE
    assert set(agents[1:4]) == {
        PipelineNode.VISION,
        PipelineNode.FRAUD,
        PipelineNode.POLICY,
    }
    assert agents[4] == PipelineNode.ADJUDICATOR
    assert agents[5] == PipelineNode.AUTO_RESOLVE


def test_invoke_routes_to_human_when_confidence_is_low(
    mocked_llm_responses: dict[str, object],
) -> None:
    verdict: TriageVerdict = mocked_llm_responses["verdict"]  # type: ignore[assignment]
    responses = dict(mocked_llm_responses)
    responses["verdict"] = verdict.model_copy(
        update={
            "overall_confidence": 0.40,
            "fraud_risk_score": 0.10,
            "routing": RoutingDecision.AUTO_RESOLVE,
            "human_review_required": False,
            "routing_reasons": [],
        }
    )
    fraud: FraudSignal = responses["fraud"]  # type: ignore[assignment]
    responses["fraud"] = fraud.model_copy(update={"fraud_risk_score": 0.10})

    compiled = build_claim_pipeline(agents=_stub_agents(responses))
    claim: ClaimIntake = responses["intake"]  # type: ignore[assignment]
    result = compiled.invoke(empty_claim_state(str(claim.claim_id)))

    assert result["requires_human_review"] is True
    assert result["verdict"].routing == RoutingDecision.HUMAN_REVIEW
    assert result["trace"][-1].agent == PipelineNode.ROUTE_TO_HUMAN
    assert any("confidence" in reason for reason in result["verdict"].routing_reasons)


def test_decide_route_thresholds() -> None:
    gates = RoutingThresholds(confidence=0.65, fraud_score=0.45)
    missing = empty_claim_state("c1")
    assert decide_route(missing, gates) == "route_to_human"

    errored = empty_claim_state("c1")
    errored["error"] = "intake exploded"
    assert decide_route(errored, gates) == "route_to_human"


def test_decide_route_numeric_gates(mocked_llm_responses: dict[str, object]) -> None:
    gates = RoutingThresholds(confidence=0.65, fraud_score=0.45)
    base: TriageVerdict = mocked_llm_responses["verdict"]  # type: ignore[assignment]

    def state_with(*, confidence: float, fraud: float) -> ClaimState:
        payload = empty_claim_state("c1")
        payload["verdict"] = base.model_copy(
            update={
                "overall_confidence": confidence,
                "fraud_risk_score": fraud,
                "routing": RoutingDecision.AUTO_RESOLVE,
                "human_review_required": False,
                "routing_reasons": [],
            }
        )
        return payload

    assert decide_route(state_with(confidence=0.65, fraud=0.45), gates) == "auto_resolve"
    assert decide_route(state_with(confidence=0.649, fraud=0.10), gates) == "route_to_human"
    assert decide_route(state_with(confidence=0.90, fraud=0.451), gates) == "route_to_human"
