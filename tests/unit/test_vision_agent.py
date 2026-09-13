from pathlib import Path

from claimguard.agents.vision_agent import run_vision_agent
from claimguard.schemas.common import DamageType
from claimguard.schemas.graph import ImageRef, empty_claim_state


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
