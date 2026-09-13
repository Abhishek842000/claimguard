from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from claimguard.agents.vision_agent import run_vision_agent
from claimguard.schemas.common import DamageType, IncidentType, Money
from claimguard.schemas.graph import ImageRef, empty_claim_state
from claimguard.schemas.intake import ClaimantProfile, ClaimIntake, IncidentDetails


def test_vision_agent_uses_filename_heuristic(tmp_path: Path) -> None:
    photo = tmp_path / "hail-1.jpg"
    photo.write_bytes(b"not-a-real-jpeg")
    state = empty_claim_state(
        "11111111-1111-4111-8111-111111111111",
        raw_images=[
            ImageRef(
                image_id="33333333-3333-4333-8333-333333333333",
                filename=photo.name,
                storage_uri=photo.resolve().as_uri(),
                caption="golf-ball hail dent",
            )
        ],
    )
    update = run_vision_agent(state)
    assessment = update["damage_assessment"]
    assert assessment is not None
    assert DamageType.DENT in assessment.photo_findings[0].damage_types
    assert update["trace"][0].agent == "vision_agent"
    assert update["trace"][0].output_schema == "DamageAssessment"


def test_vision_uses_intake_notes_when_filename_is_generic(tmp_path: Path) -> None:
    photo = tmp_path / "demo_img.webp"
    photo.write_bytes(b"not-a-real-image")
    state = empty_claim_state(
        "11111111-1111-4111-8111-111111111111",
        raw_images=[
            ImageRef(
                image_id="33333333-3333-4333-8333-333333333333",
                filename=photo.name,
                storage_uri=photo.resolve().as_uri(),
            )
        ],
    )
    state["intake"] = ClaimIntake(
        claim_id="11111111-1111-4111-8111-111111111111",
        policy_number="PA-2026-000039",
        claimant=ClaimantProfile(full_name="Jordan Hale"),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_WEATHER,
            incident_date=date(2026, 6, 12),
            description="Hood and roof dented.",
        ),
        claimed_amount=Money(amount=Decimal("6225.00")),
        adjuster_notes="Golf-ball hail in Phoenix dented the hood and roof.",
        intake_confidence=0.9,
        created_at=datetime.now(UTC),
    )
    update = run_vision_agent(state)
    assessment = update["damage_assessment"]
    assert assessment is not None
    assert DamageType.DENT in assessment.photo_findings[0].damage_types
    assert assessment.confidence >= 0.62
