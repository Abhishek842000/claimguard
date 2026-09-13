"""Schema contracts: fixtures must instantiate, and invariants must hold."""

from decimal import Decimal

import pytest
from claimguard.schemas import ClaimIntake, FraudSignal, TriageVerdict
from claimguard.schemas.common import RoutingDecision
from pydantic import ValidationError


def test_sample_claim_is_valid(sample_claim: ClaimIntake) -> None:
    assert sample_claim.policy_number == "PA-2024-009188"
    assert sample_claim.claimed_amount.amount == Decimal("4850.00")
    assert sample_claim.incident.vehicle is not None
    dumped = sample_claim.model_dump()
    assert ClaimIntake.model_validate(dumped).claim_id == sample_claim.claim_id


def test_mocked_agent_outputs_validate(mocked_llm_responses: dict[str, object]) -> None:
    assert isinstance(mocked_llm_responses["intake"], ClaimIntake)
    assert isinstance(mocked_llm_responses["fraud"], FraudSignal)
    verdict = mocked_llm_responses["verdict"]
    assert isinstance(verdict, TriageVerdict)
    assert verdict.routing == RoutingDecision.HUMAN_REVIEW
    assert verdict.human_review_required is True


def test_blank_policy_number_rejected(sample_claim: ClaimIntake) -> None:
    payload = sample_claim.model_dump()
    payload["policy_number"] = "   "
    with pytest.raises(ValidationError):
        ClaimIntake.model_validate(payload)


def test_verdict_rejects_mismatched_review_flag(mocked_llm_responses: dict[str, object]) -> None:
    verdict: TriageVerdict = mocked_llm_responses["verdict"]  # type: ignore[assignment]
    payload = verdict.model_dump()
    payload["human_review_required"] = False
    with pytest.raises(ValidationError, match="human_review_required"):
        TriageVerdict.model_validate(payload)


def test_extra_fields_rejected_at_agent_boundary(sample_claim: ClaimIntake) -> None:
    payload = sample_claim.model_dump()
    payload["debug_scratchpad"] = "free text must not leak across agents"
    with pytest.raises(ValidationError):
        ClaimIntake.model_validate(payload)
