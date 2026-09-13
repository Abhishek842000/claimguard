"""Schemas produced by the intake agent after document / note normalization."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator

from claimguard.schemas.common import (
    ClaimGuardModel,
    DocumentType,
    GeoLocation,
    IncidentType,
    Money,
    UnitInterval,
)


class ClaimantProfile(ClaimGuardModel):
    """Synthetic claimant identity attached to a claim. All fields are PII."""

    full_name: str = Field(
        description="Claimant display name. Synthetic only. PII — redact before logging.",
    )
    email: str | None = Field(
        default=None,
        description="Contact email if present on the form. PII — redact before logging.",
    )
    phone: str | None = Field(
        default=None,
        description="Contact phone if present on the form. PII — redact before logging.",
    )
    date_of_birth: date | None = Field(
        default=None,
        description="Date of birth when the form includes it. PII — redact before logging.",
    )


class VehicleInfo(ClaimGuardModel):
    """Vehicle identifiers used by fraud entity-matching and policy VIN checks."""

    year: int | None = Field(default=None, ge=1950, le=2100, description="Model year.")
    make: str | None = Field(default=None, description="Manufacturer, e.g. Toyota.")
    model: str | None = Field(default=None, description="Model name, e.g. Camry.")
    vin: str | None = Field(
        default=None,
        description="17-character VIN when extracted. PII-adjacent — hash or mask in logs.",
    )
    license_plate: str | None = Field(
        default=None,
        description="Plate number if extracted. PII — redact before logging.",
    )


class IncidentDetails(ClaimGuardModel):
    """Normalized loss event. Downstream agents must not re-parse raw notes for these fields."""

    incident_type: IncidentType = Field(
        description="Peril classification used to select policy sections and required docs.",
    )
    incident_date: date = Field(description="Date the loss occurred, not the filing date.")
    reported_date: date | None = Field(
        default=None,
        description="Date the insured reported the loss to the carrier, if known.",
    )
    description: str = Field(
        min_length=1,
        description="Free-text loss narrative after OCR / note extraction, still possibly noisy.",
    )
    location: GeoLocation | None = Field(
        default=None,
        description="Where the incident happened, when the form or notes include it.",
    )
    third_party_involved: bool = Field(
        default=False,
        description="True when another driver, property owner, or claimant is named.",
    )
    police_report_number: str | None = Field(
        default=None,
        description="Agency report number if cited. Useful as a fraud-graph entity.",
    )
    vehicle: VehicleInfo | None = Field(
        default=None,
        description="Populated for auto perils; omitted for pure property claims.",
    )


class ExtractedEntity(ClaimGuardModel):
    """A single NER span. Values may be PII; redaction happens at the logging boundary."""

    entity_type: str = Field(
        description="Label such as PERSON, ORG, DATE, MONEY, VIN, POLICY_NUMBER, ADDRESS.",
    )
    value: str = Field(description="Raw extracted string, not normalized.")
    start_char: int | None = Field(
        default=None,
        ge=0,
        description="Start offset in the source text, if the extractor provided offsets.",
    )
    end_char: int | None = Field(
        default=None,
        ge=0,
        description="End offset in the source text, exclusive.",
    )
    confidence: UnitInterval = Field(
        description="Extractor confidence in [0, 1].",
    )
    source_document_id: UUID | None = Field(
        default=None,
        description="Document this span was taken from, when known.",
    )


class ClaimDocumentRef(ClaimGuardModel):
    """Pointer to an ingested file plus a short extract for agent context windows."""

    document_id: UUID = Field(description="Primary key of claim_documents.")
    document_type: DocumentType = Field(
        description="Predicted or user-declared document class.",
    )
    filename: str = Field(description="Original upload filename (not a storage path).")
    storage_uri: str = Field(
        description="Internal URI (local volume or object storage) used by the worker.",
    )
    page_count: int | None = Field(
        default=None,
        ge=1,
        description="PDF page count after parse; null for non-paginated files.",
    )
    extracted_text_preview: str | None = Field(
        default=None,
        max_length=2000,
        description="First ~2k characters of extracted text for debugging and traces.",
    )


class ClaimImageRef(ClaimGuardModel):
    """Pointer to a damage photo the vision agent will classify."""

    image_id: UUID = Field(description="Primary key of claim_images.")
    filename: str = Field(description="Original upload filename.")
    storage_uri: str = Field(description="Internal URI for the bytes on disk / object storage.")
    caption: str | None = Field(
        default=None,
        description="Optional submitter caption (e.g. 'front bumper, passenger side').",
    )


class IntakeExtraction(ClaimGuardModel):
    """LLM-facing extract. The agent attaches claim_id, file refs, and parser versions.

    This is the schema `generate_structured` validates — not ClaimIntake — so the
    model cannot invent storage URIs or document ids.
    """

    policy_number: str | None = Field(
        default=None,
        description="Policy number as printed. Null if not present in the source text.",
    )
    claimant: ClaimantProfile = Field(description="Named insured / claimant. Entire object is PII.")
    incident: IncidentDetails = Field(description="Normalized loss event.")
    claimed_amount: Money | None = Field(
        default=None,
        description="Amount requested on the form. Null if not stated.",
    )
    extracted_entities: list[ExtractedEntity] = Field(
        default_factory=list,
        description="Entities the model spotted that the regex NER may have missed.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Dotted paths the source text did not support, e.g. 'incident.vehicle.vin'.",
    )
    intake_confidence: UnitInterval = Field(
        description="How complete and internally consistent this extract is.",
    )


class ClaimIntake(ClaimGuardModel):
    """Canonical claim record after intake. This is the only unstructured-to-structured hop."""

    claim_id: UUID = Field(description="Stable ClaimGuard identifier for this submission.")
    policy_number: str = Field(
        description="Carrier policy number as printed on the form or declarations page.",
    )
    claimant: ClaimantProfile = Field(description="Who is filing. Entire object is PII.")
    incident: IncidentDetails = Field(description="Normalized loss event.")
    claimed_amount: Money = Field(
        description="Amount the insured is asking for, not the recommended payout.",
    )
    adjuster_notes: str = Field(
        default="",
        description="Concatenated adjuster / FNOL notes after text extraction. May be empty.",
    )
    documents: list[ClaimDocumentRef] = Field(
        default_factory=list,
        description="All non-image files attached to the submission.",
    )
    images: list[ClaimImageRef] = Field(
        default_factory=list,
        description="Damage photos routed to the vision agent.",
    )
    extracted_entities: list[ExtractedEntity] = Field(
        default_factory=list,
        description="NER spans used by fraud entity-matching.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Intake fields that could not be filled from the documents (dotted paths).",
    )
    intake_confidence: UnitInterval = Field(
        description="How complete and internally consistent the normalized record is.",
    )
    parser_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Parser / OCR / NER component versions, e.g. {'ocr': 'tesseract-5.4'}.",
    )
    created_at: datetime = Field(
        description="UTC timestamp when intake produced this object.",
    )

    @field_validator("policy_number")
    @classmethod
    def policy_number_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_number must not be blank")
        return value.strip()
