from datetime import UTC, date, datetime
from decimal import Decimal

from claimguard.agents.adjudicator_agent import run_adjudicator_agent
from claimguard.llm.structured_output import scripted_completer
from claimguard.schemas.common import CoverageStatus, IncidentType, Money, RoutingDecision
from claimguard.schemas.fraud import FraudSignal
from claimguard.schemas.graph import empty_claim_state
from claimguard.schemas.intake import ClaimantProfile, ClaimIntake, IncidentDetails
from claimguard.schemas.policy import PolicyDetermination
from claimguard.schemas.verdict import SettlementMemo


def test_adjudicator_flags_human_review_on_high_fraud() -> None:
    intake = ClaimIntake(
        claim_id="11111111-1111-4111-8111-111111111111",
        policy_number="PA-2026-000039",
        claimant=ClaimantProfile(full_name="Casey Patel"),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_WEATHER,
            incident_date=date(2026, 6, 12),
            description="Hail.",
        ),
        claimed_amount=Money(amount=Decimal("6225.00")),
        intake_confidence=0.9,
        created_at=datetime.now(UTC),
    )
    state = empty_claim_state(str(intake.claim_id))
    state["intake"] = intake
    state["fraud_signal"] = FraudSignal(
        claim_id=intake.claim_id,
        fraud_risk_score=0.72,
        risk_tier="high",
        justification="FR-WEATHER-MISMATCH",
        confidence=0.8,
    )
    state["policy_determination"] = PolicyDetermination(
        claim_id=intake.claim_id,
        coverage_status=CoverageStatus.COVERED,
        rationale="OTC hail",
        confidence=0.8,
    )
    memo = SettlementMemo(summary="Hold for weather review.")
    update = run_adjudicator_agent(
        state,
        completer=scripted_completer([memo.model_dump_json()]),
    )
    verdict = update["verdict"]
    assert verdict is not None
    assert verdict.human_review_required is True
    assert verdict.routing == RoutingDecision.HUMAN_REVIEW
    assert any("fraud_score" in reason for reason in verdict.routing_reasons)
