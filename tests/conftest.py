"""Shared fixtures: sample claim, mocked LLM payloads, and a test database."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from claimguard.config import get_settings
from claimguard.schemas.common import (
    CoverageStatus,
    DamageType,
    DocumentType,
    IncidentType,
    Money,
    RetrievalSource,
    RiskTier,
    RoutingDecision,
    SeverityLevel,
)
from claimguard.schemas.damage import DamageAssessment, PhotoFinding
from claimguard.schemas.fraud import FraudRuleHit, FraudSignal, SimilarFraudCase
from claimguard.schemas.intake import (
    ClaimantProfile,
    ClaimDocumentRef,
    ClaimImageRef,
    ClaimIntake,
    ExtractedEntity,
    GeoLocation,
    IncidentDetails,
    VehicleInfo,
)
from claimguard.schemas.policy import CitedClause, PolicyDetermination
from claimguard.schemas.verdict import MissingDocument, SettlementMemo, TriageVerdict
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SAMPLE_CLAIM_ID = UUID("11111111-1111-4111-8111-111111111111")
SAMPLE_DOC_ID = UUID("22222222-2222-4222-8222-222222222222")
SAMPLE_IMAGE_ID = UUID("33333333-3333-4333-8333-333333333333")


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sample_claim() -> ClaimIntake:
    """Synthetic auto-collision claim used across unit tests. No real PII."""
    return ClaimIntake(
        claim_id=SAMPLE_CLAIM_ID,
        policy_number="PA-2024-009188",
        claimant=ClaimantProfile(
            full_name="Jordan Hale",
            email="jordan.hale@example.test",
            phone="415-555-0148",
            date_of_birth=date(1988, 4, 12),
        ),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_COLLISION,
            incident_date=date(2026, 8, 3),
            reported_date=date(2026, 8, 4),
            description=(
                "Insured reports being rear-ended at a red light on Market St. "
                "Visible bumper and taillight damage. No airbag deployment. "
                "Other driver provided insurance; police report not yet attached."
            ),
            location=GeoLocation(
                city="San Francisco",
                state="CA",
                postal_code="94103",
                street_address="500 Market St",
            ),
            third_party_involved=True,
            police_report_number=None,
            vehicle=VehicleInfo(
                year=2019,
                make="Toyota",
                model="Camry",
                vin="4T1B11HK5KU123456",
                license_plate="7XYZ123",
            ),
        ),
        claimed_amount=Money(amount=Decimal("4850.00")),
        adjuster_notes=(
            "FNOL via mobile app. Photos look consistent with a low-speed rear impact. "
            "Ask for the police report and the body-shop estimate before settling."
        ),
        documents=[
            ClaimDocumentRef(
                document_id=SAMPLE_DOC_ID,
                document_type=DocumentType.CLAIM_FORM,
                filename="fnol-claim-form.pdf",
                storage_uri="file:///data/synthetic_claims/11111111/fnol-claim-form.pdf",
                page_count=3,
                extracted_text_preview="ACME Personal Auto Claim Form ... policy PA-2024-009188",
            )
        ],
        images=[
            ClaimImageRef(
                image_id=SAMPLE_IMAGE_ID,
                filename="rear-bumper.jpg",
                storage_uri="file:///data/synthetic_claims/11111111/rear-bumper.jpg",
                caption="rear bumper, passenger side",
            )
        ],
        extracted_entities=[
            ExtractedEntity(
                entity_type="POLICY_NUMBER",
                value="PA-2024-009188",
                confidence=0.99,
                source_document_id=SAMPLE_DOC_ID,
            ),
            ExtractedEntity(
                entity_type="VIN",
                value="4T1B11HK5KU123456",
                confidence=0.91,
                source_document_id=SAMPLE_DOC_ID,
            ),
        ],
        missing_fields=["incident.police_report_number"],
        intake_confidence=0.86,
        parser_versions={"ocr": "stub-phase0", "ner": "stub-phase0"},
        created_at=datetime(2026, 8, 4, 17, 30, tzinfo=UTC),
    )


@pytest.fixture
def mocked_llm_responses(sample_claim: ClaimIntake) -> dict[str, object]:
    """Valid structured payloads as if each agent had already succeeded."""
    damage = DamageAssessment(
        claim_id=sample_claim.claim_id,
        overall_severity=SeverityLevel.MODERATE,
        severity_score=0.42,
        estimated_repair_low=Money(amount=Decimal("2100.00")),
        estimated_repair_high=Money(amount=Decimal("3600.00")),
        photo_findings=[
            PhotoFinding(
                image_id=SAMPLE_IMAGE_ID,
                damage_types=[DamageType.DENT, DamageType.BROKEN_LIGHT],
                severity=SeverityLevel.MODERATE,
                consistency_notes="Rear-end damage matches the described collision.",
                confidence=0.81,
            )
        ],
        narrative="Moderate rear-end cosmetic and lighting damage; no structural cues.",
        inconsistencies=[],
        model_name="stub/damage-classifier",
        model_version="phase0",
        confidence=0.81,
    )
    fraud = FraudSignal(
        claim_id=sample_claim.claim_id,
        fraud_risk_score=0.18,
        risk_tier=RiskTier.LOW,
        rule_hits=[
            FraudRuleHit(
                rule_id="FR-MISSING-POLICE-REPORT",
                rule_name="Police report referenced but not attached",
                severity="low",
                detail="third_party_involved is true and police_report_number is null.",
            )
        ],
        similar_cases=[
            SimilarFraudCase(
                case_id="fraud-pattern-low-speed-inflate-01",
                similarity=0.44,
                source=RetrievalSource.RERANK,
                excerpt="Low-speed rear impacts with inflated repair estimates.",
                citation="Synthetic fraud corpus §A.3",
            )
        ],
        entity_matches=[],
        justification=(
            "Rule FR-MISSING-POLICE-REPORT fired. Similar case "
            "fraud-pattern-low-speed-inflate-01 is only weakly related. "
            "No shared-entity graph hits. Overall risk remains low."
        ),
        retrieved_chunk_ids=["fraud-pattern-low-speed-inflate-01"],
        grounded=True,
        confidence=0.77,
    )
    policy = PolicyDetermination(
        claim_id=sample_claim.claim_id,
        coverage_status=CoverageStatus.COVERED,
        covered_perils=["collision"],
        supporting_clauses=[
            CitedClause(
                document_id="pap-pp0001",
                document_title="Personal Auto Policy PP 00 01 09 18",
                clause_id="pap-pp0001-partd-insuring",
                section="Part D — Coverage For Damage To Your Auto",
                quote=(
                    "We will pay for direct and accidental loss to your covered auto "
                    "caused by collision."
                ),
                page=12,
                relevance=0.93,
                source=RetrievalSource.RERANK,
            )
        ],
        exclusions_applied=[],
        deductible=Money(amount=Decimal("500.00")),
        coverage_limit=Money(amount=Decimal("50000.00")),
        estimated_payable=Money(amount=Decimal("4350.00")),
        rationale=(
            "Collision is a covered peril under Part D (clause pap-pp0001-partd-insuring). "
            "No exclusion chunk was retrieved that applies to a third-party rear-end impact."
        ),
        information_gaps=["police_report"],
        retrieved_chunk_ids=["pap-pp0001-partd-insuring"],
        grounded=True,
        confidence=0.84,
    )
    verdict = TriageVerdict(
        claim_id=sample_claim.claim_id,
        severity_score=damage.severity_score,
        fraud_risk_score=fraud.fraud_risk_score,
        coverage=policy,
        missing_documents=[
            MissingDocument(
                document_type=DocumentType.POLICE_REPORT,
                reason="Third-party collision with no report number or attachment.",
                required_for="compliance",
                blocking=True,
            )
        ],
        settlement_memo=SettlementMemo(
            summary=(
                "Covered collision with moderate rear-end damage. "
                "Hold payment until the police report is on file."
            ),
            recommended_payout=None,
            conditions=["Receive police report"],
            caveats=["Repair range is a vision heuristic, not a shop estimate."],
        ),
        routing=RoutingDecision.HUMAN_REVIEW,
        routing_reasons=["blocking missing document: police_report"],
        overall_confidence=0.77,
        human_review_required=True,
        prompt_versions={
            "intake": "intake_v1",
            "fraud": "fraud_v1",
            "policy": "policy_v1",
            "adjudicator": "adjudicator_v1",
        },
        model_routing={"intake": "cheap", "fraud": "frontier", "policy": "cheap"},
    )
    return {
        "intake": sample_claim,
        "damage": damage,
        "fraud": fraud,
        "policy": policy,
        "verdict": verdict,
    }


@pytest.fixture
def test_db(tmp_path) -> Engine:
    """File-backed SQLite engine for tests that only need a real DB connection.

    Postgres-specific types (JSONB, VECTOR) are not created here. Integration
    tests against Docker Postgres live under tests/integration/.
    """
    engine = create_engine(f"sqlite:///{tmp_path}/claimguard-test.db", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE smoke (id INTEGER PRIMARY KEY)"))
        conn.execute(text("INSERT INTO smoke (id) VALUES (1)"))
    return engine
