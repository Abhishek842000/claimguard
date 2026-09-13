from datetime import UTC, date, datetime
from decimal import Decimal

from claimguard.agents.fraud_agent import run_fraud_agent
from claimguard.fraud.rules import evaluate_fraud_rules
from claimguard.llm.structured_output import scripted_completer
from claimguard.retrieval.hybrid_retriever import InMemoryRetriever, RetrievedChunk
from claimguard.schemas.common import IncidentType, Money, RetrievalSource
from claimguard.schemas.fraud import FraudSignal
from claimguard.schemas.graph import empty_claim_state
from claimguard.schemas.intake import ClaimantProfile, ClaimIntake, GeoLocation, IncidentDetails


def _weather_intake() -> ClaimIntake:
    return ClaimIntake(
        claim_id="11111111-1111-4111-8111-111111111111",
        policy_number="PA-2026-000039",
        claimant=ClaimantProfile(full_name="Casey Patel"),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_WEATHER,
            incident_date=date(2026, 6, 12),
            description="Golf-ball hail in Phoenix.",
            location=GeoLocation(city="Phoenix", state="AZ"),
            third_party_involved=True,
        ),
        claimed_amount=Money(amount=Decimal("6225.00")),
        intake_confidence=0.9,
        created_at=datetime.now(UTC),
    )


def test_weather_mismatch_rule_fires_for_phoenix_hail() -> None:
    hits = evaluate_fraud_rules(_weather_intake())
    assert any(hit.rule_id == "FR-WEATHER-MISMATCH" for hit in hits)
    assert any(hit.rule_id == "FR-MISSING-POLICE-REPORT" for hit in hits)


def test_fraud_agent_retries_malformed_llm_then_succeeds() -> None:
    intake = _weather_intake()
    state = empty_claim_state(str(intake.claim_id))
    state["intake"] = intake
    retriever = InMemoryRetriever(
        [
            RetrievedChunk(
                chunk_id="fraud-05-weather-mismatch:0",
                title="weather",
                text="hail claim with no NOAA storm",
                score=0.8,
                source=RetrievalSource.BM25,
            )
        ]
    )
    good = run_fraud_agent(state, retriever=retriever)["fraud_signal"]
    assert good is not None
    completer = scripted_completer(["not-json", good.model_dump_json()])
    update = run_fraud_agent(state, completer=completer, retriever=retriever)
    signal = update["fraud_signal"]
    assert isinstance(signal, FraudSignal)
    assert update["trace"][0].metadata["attempts"] == 2
