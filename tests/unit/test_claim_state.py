"""ClaimState is the LangGraph backbone — keys and reducers must stay exact."""

from __future__ import annotations

from typing import get_type_hints

from claimguard.schemas.graph import (
    AgentStep,
    ClaimState,
    DocumentRef,
    GraphState,
    ImageRef,
    coalesce_error,
    empty_claim_state,
)
from claimguard.schemas.intake import ClaimIntake

CLAIM_STATE_KEYS = {
    "claim_id",
    "raw_documents",
    "raw_images",
    "intake",
    "damage_assessment",
    "fraud_signal",
    "policy_determination",
    "verdict",
    "trace",
    "requires_human_review",
    "error",
}


def test_claim_state_keys_match_spec() -> None:
    assert set(ClaimState.__required_keys__) == CLAIM_STATE_KEYS
    assert ClaimState.__optional_keys__ == frozenset()


def test_empty_claim_state_initializes_every_key() -> None:
    docs = [
        DocumentRef(
            document_id="doc-1",
            filename="fnol.pdf",
            storage_uri="file:///data/fnol.pdf",
        )
    ]
    images = [
        ImageRef(
            image_id="img-1",
            filename="bumper.jpg",
            storage_uri="file:///data/bumper.jpg",
            caption="rear bumper",
        )
    ]
    state = empty_claim_state("claim-1", raw_documents=docs, raw_images=images)
    assert set(state) == CLAIM_STATE_KEYS
    assert state["claim_id"] == "claim-1"
    assert state["raw_documents"] == docs
    assert state["raw_images"] == images
    assert state["intake"] is None
    assert state["damage_assessment"] is None
    assert state["fraud_signal"] is None
    assert state["policy_determination"] is None
    assert state["verdict"] is None
    assert state["trace"] == []
    assert state["requires_human_review"] is False
    assert state["error"] is None


def test_graph_state_round_trips_to_claim_state(sample_claim: ClaimIntake) -> None:
    snapshot = GraphState(
        claim_id=str(sample_claim.claim_id),
        intake=sample_claim,
        requires_human_review=False,
    )
    state = snapshot.to_claim_state()
    assert state["claim_id"] == str(sample_claim.claim_id)
    assert state["intake"] is sample_claim
    assert state["trace"] == []


def test_trace_reducer_is_operator_add() -> None:
    hints = get_type_hints(ClaimState, include_extras=True)
    metadata = getattr(hints["trace"], "__metadata__", ())
    assert metadata, "trace must be Annotated with a list reducer for parallel writes"
    reducer = metadata[0]
    left = [AgentStep.completed("intake_agent")]
    right = [AgentStep.completed("vision_agent")]
    merged = reducer(left, right)
    assert [step.agent for step in merged] == ["intake_agent", "vision_agent"]


def test_error_reducer_keeps_first_message() -> None:
    assert coalesce_error("vision failed", "fraud failed") == "vision failed"
    assert coalesce_error(None, "fraud failed") == "fraud failed"
    assert coalesce_error(None, None) is None
