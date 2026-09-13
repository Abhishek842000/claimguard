"""Intake agent: happy path and malformed-output retry, all LLM calls mocked."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from claimguard.agents.intake_agent import (
    intake_input_from_claim_dir,
    run_intake,
    run_intake_agent,
)
from claimguard.llm.structured_output import scripted_completer
from claimguard.schemas.common import IncidentType, Money
from claimguard.schemas.graph import empty_claim_state
from claimguard.schemas.intake import ClaimantProfile, IncidentDetails, IntakeExtraction

SAMPLE_DIR = Path("data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6")


def _extraction() -> IntakeExtraction:
    return IntakeExtraction(
        policy_number="PA-2026-000039",
        claimant=ClaimantProfile(
            full_name="Casey Patel",
            email="casey.patel.39@example.test",
            phone="541-555-4990",
        ),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_WEATHER,
            incident_date=date(2026, 6, 12),
            description="Golf-ball hail dented every horizontal panel in Phoenix.",
            third_party_involved=True,
        ),
        claimed_amount=Money(amount=Decimal("6225.00")),
        missing_fields=[],
        intake_confidence=0.88,
    )


def test_intake_happy_path_with_mocked_llm() -> None:
    payload = intake_input_from_claim_dir(SAMPLE_DIR)
    update = run_intake(
        payload,
        completer=scripted_completer([_extraction().model_dump_json()]),
    )
    assert update.get("error") is None
    intake = update["intake"]
    assert intake is not None
    assert intake.policy_number == "PA-2026-000039"
    assert intake.claimant.full_name == "Casey Patel"
    assert intake.incident.incident_type == IncidentType.AUTO_WEATHER
    assert intake.claimed_amount.amount == Decimal("6225.00")
    assert intake.adjuster_notes.startswith("First notice received")
    assert any("PA-2026-000039" in entity.value for entity in intake.extracted_entities)
    assert update["trace"][0].status == "ok"
    assert update["trace"][0].metadata["attempts"] == 1


def test_intake_malformed_output_triggers_retry() -> None:
    payload = intake_input_from_claim_dir(SAMPLE_DIR)
    completer = scripted_completer(
        [
            json.dumps({"policy_number": "PA-2026-000039", "debug_scratchpad": "nope"}),
            _extraction().model_dump_json(),
        ]
    )
    update = run_intake(payload, completer=completer)
    assert update["intake"] is not None
    assert update["trace"][0].metadata["attempts"] == 2
    assert update["intake"].policy_number == "PA-2026-000039"


def test_intake_exhausted_retries_flags_human_review() -> None:
    payload = intake_input_from_claim_dir(SAMPLE_DIR)
    update = run_intake(
        payload,
        completer=scripted_completer(["not-json", "{}", "{}"]),
    )
    assert update.get("intake") is None
    assert update["requires_human_review"] is True
    assert update["error"] is not None
    assert "exhausted" in update["error"]
    assert update["trace"][0].status == "error"


def test_run_intake_agent_reads_claim_state() -> None:
    payload = intake_input_from_claim_dir(SAMPLE_DIR)
    state = empty_claim_state(
        payload.claim_id,
        raw_documents=payload.raw_documents,
        raw_images=payload.raw_images,
    )
    update = run_intake_agent(
        state,
        completer=scripted_completer([_extraction().model_dump_json()]),
    )
    assert update["intake"] is not None
    assert str(update["intake"].claim_id) == payload.claim_id


def test_intake_heuristic_standalone_path_extracts_sample_fnol() -> None:
    """No completer → heuristic completer. Used for manual sample inspection."""

    payload = intake_input_from_claim_dir(SAMPLE_DIR)
    update = run_intake(payload)
    intake = update["intake"]
    assert intake is not None
    assert intake.policy_number == "PA-2026-000039"
    assert intake.claimant.full_name == "Casey Patel"
    assert intake.incident.incident_date == date(2026, 6, 12)
    assert intake.claimed_amount.amount == Decimal("6225.00")
