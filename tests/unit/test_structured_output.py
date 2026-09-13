"""Instructor-style validate → repair → exhaust must stay visible and testable."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from claimguard.llm.structured_output import generate_structured, scripted_completer
from claimguard.schemas.common import IncidentType, Money
from claimguard.schemas.intake import ClaimantProfile, IncidentDetails, IntakeExtraction


def _valid_extraction() -> IntakeExtraction:
    return IntakeExtraction(
        policy_number="PA-2026-000039",
        claimant=ClaimantProfile(full_name="Casey Patel"),
        incident=IncidentDetails(
            incident_type=IncidentType.AUTO_WEATHER,
            incident_date=date(2026, 6, 12),
            description="Hail dented horizontal panels in Phoenix.",
        ),
        claimed_amount=Money(amount=Decimal("6225.00")),
        missing_fields=[],
        intake_confidence=0.84,
    )


def test_generate_structured_happy_path() -> None:
    extraction = _valid_extraction()
    result = generate_structured(
        "extract",
        IntakeExtraction,
        completer=scripted_completer([extraction.model_dump_json()]),
        system="test",
    )
    assert result.ok is True
    assert result.exhausted is False
    assert result.attempts == 1
    assert result.value is not None
    assert result.value.policy_number == "PA-2026-000039"


def test_generate_structured_retries_after_malformed_output() -> None:
    extraction = _valid_extraction()
    completer = scripted_completer(
        [
            '{"policy_number": "PA-2026-000039"}',
            extraction.model_dump_json(),
        ]
    )
    result = generate_structured("extract", IntakeExtraction, completer=completer)
    assert result.ok is True
    assert result.attempts == 2
    assert result.errors
    assert result.value is not None
    assert result.value.claimant.full_name == "Casey Patel"


def test_generate_structured_exhausts_and_flags_human_review() -> None:
    completer = scripted_completer(
        [
            "not json",
            '{"debug": true}',
            '{"policy_number": ""}',
        ]
    )
    result = generate_structured(
        "extract",
        IntakeExtraction,
        completer=completer,
        max_retries=2,
    )
    assert result.ok is False
    assert result.exhausted is True
    assert result.requires_human_review is True
    assert result.attempts == 3
    assert result.value is None
    assert len(result.errors) == 3
