from claimguard.graph.claim_pipeline import PipelineAgents
from claimguard.graph.runtime import invoke_claim_pipeline
from claimguard.observability.langfuse import NullSink
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate, empty_claim_state


def test_agent_exception_routes_to_human_without_crashing() -> None:
    def boom(state: ClaimState) -> ClaimStateUpdate:
        raise RuntimeError("vision exploded")

    def passthrough(output_key: str):
        def node(state: ClaimState) -> ClaimStateUpdate:
            return {"trace": [AgentStep.completed(output_key)]}

        return node

    from pathlib import Path

    from claimguard.agents.adjudicator_agent import run_adjudicator_agent
    from claimguard.agents.fraud_agent import run_fraud_agent
    from claimguard.agents.intake_agent import intake_input_from_claim_dir, run_intake_agent
    from claimguard.agents.policy_agent import run_policy_agent

    payload = intake_input_from_claim_dir(
        Path("data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6")
    )
    state = empty_claim_state(
        payload.claim_id,
        raw_documents=payload.raw_documents,
        raw_images=payload.raw_images,
    )
    agents = PipelineAgents(
        intake_agent=run_intake_agent,
        vision_agent=boom,
        fraud_agent=run_fraud_agent,
        policy_agent=run_policy_agent,
        adjudicator_agent=run_adjudicator_agent,
    )
    result = invoke_claim_pipeline(state, agents=agents, sink=NullSink())
    assert result["error"] is not None
    assert "vision exploded" in result["error"]
    assert result["requires_human_review"] is True
    assert result["verdict"] is not None
    assert result["verdict"].human_review_required is True
    assert any(step.agent == "vision_agent" and step.status == "error" for step in result["trace"])


def test_full_pipeline_on_sample_claim() -> None:
    from pathlib import Path

    from claimguard.agents.intake_agent import intake_input_from_claim_dir

    payload = intake_input_from_claim_dir(
        Path("data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6")
    )
    state = empty_claim_state(
        payload.claim_id,
        raw_documents=payload.raw_documents,
        raw_images=payload.raw_images,
    )
    result = invoke_claim_pipeline(state, sink=NullSink())
    assert result["intake"] is not None
    assert result["damage_assessment"] is not None
    assert result["fraud_signal"] is not None
    assert result["policy_determination"] is not None
    assert result["verdict"] is not None
    agents = [step.agent for step in result["trace"]]
    assert agents[0] == "intake_agent"
    assert {"vision_agent", "fraud_agent", "policy_agent"} <= set(agents)
    assert "adjudicator_agent" in agents
    assert agents[-1] in {"route_to_human", "auto_resolve"}
    assert all(step.input_snapshot for step in result["trace"] if step.agent.endswith("_agent"))
