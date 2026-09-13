from datetime import UTC, date, datetime
from decimal import Decimal

from claimguard.agents.policy_agent import run_policy_agent
from claimguard.policy.grounding import filter_grounded_clauses
from claimguard.retrieval.hybrid_retriever import InMemoryRetriever, RetrievedChunk
from claimguard.schemas.common import CoverageStatus, IncidentType, Money, RetrievalSource
from claimguard.schemas.graph import empty_claim_state
from claimguard.schemas.intake import ClaimantProfile, ClaimIntake, IncidentDetails
from claimguard.schemas.policy import CitedClause, PolicyDetermination


def test_filter_grounded_clauses_drops_hallucinated_ids() -> None:
    determination = PolicyDetermination(
        claim_id="11111111-1111-4111-8111-111111111111",
        coverage_status=CoverageStatus.COVERED,
        supporting_clauses=[
            CitedClause(
                document_id="pap-cg-01-part-d-otc",
                document_title="OTC",
                clause_id="pap-cg-01-part-d-otc:0",
                section="Part D",
                quote="other than collision",
                relevance=0.9,
                source=RetrievalSource.RRF,
            ),
            CitedClause(
                document_id="invented",
                document_title="Hallucinated",
                clause_id="not-a-real-chunk",
                section="Nope",
                quote="we cover everything",
                relevance=0.9,
                source=RetrievalSource.RRF,
            ),
        ],
        rationale="test",
        confidence=0.7,
    )
    grounded = filter_grounded_clauses(determination, {"pap-cg-01-part-d-otc:0"})
    assert len(grounded.supporting_clauses) == 1
    assert grounded.grounded is False
    assert grounded.supporting_clauses[0].clause_id == "pap-cg-01-part-d-otc:0"


def test_policy_agent_uses_only_retrieved_clause_ids() -> None:
    intake = ClaimIntake(
        claim_id="11111111-1111-4111-8111-111111111111",
        policy_number="PA-2026-000039",
        claimant=ClaimantProfile(full_name="Casey Patel"),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_WEATHER,
            incident_date=date(2026, 6, 12),
            description="Hail dented the hood.",
        ),
        claimed_amount=Money(amount=Decimal("6225.00")),
        intake_confidence=0.9,
        created_at=datetime.now(UTC),
    )
    state = empty_claim_state(str(intake.claim_id))
    state["intake"] = intake
    retriever = InMemoryRetriever(
        [
            RetrievedChunk(
                chunk_id="pap-cg-01-part-d-otc:0",
                title="Other Than Collision",
                text="We will pay for loss caused by other than collision including hail.",
                score=0.8,
                source=RetrievalSource.BM25,
            )
        ]
    )
    update = run_policy_agent(state, retriever=retriever)
    determination = update["policy_determination"]
    assert determination is not None
    assert determination.grounded is True
    assert all(
        clause.clause_id == "pap-cg-01-part-d-otc:0" or clause.document_id == "pap-cg-01-part-d-otc"
        for clause in determination.supporting_clauses
    )
