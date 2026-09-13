"""Schemas produced by the vision agent from damage photographs."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from claimguard.schemas.common import (
    ClaimGuardModel,
    DamageType,
    Money,
    SeverityLevel,
    UnitInterval,
)


class DetectedObject(ClaimGuardModel):
    """A single object / region called out by the detector or captioner."""

    label: str = Field(description="Detector label, e.g. 'front bumper' or 'airbag'.")
    confidence: UnitInterval = Field(description="Detector confidence in [0, 1].")
    bbox_xyxy: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Normalized bounding box [x1, y1, x2, y2] in [0, 1], if available.",
    )


class PhotoFinding(ClaimGuardModel):
    """Per-image classification result. One claim may have many photos."""

    image_id: UUID = Field(description="Matches ClaimImageRef.image_id.")
    damage_types: list[DamageType] = Field(
        description="Damage labels visible in this photo. Empty if none_visible.",
    )
    severity: SeverityLevel = Field(
        description="Severity implied by this photo alone, before cross-photo aggregation.",
    )
    objects: list[DetectedObject] = Field(
        default_factory=list,
        description="Optional object-detection support for the labels above.",
    )
    consistency_notes: str = Field(
        default="",
        description="Whether this photo agrees with the claimed incident type and other photos.",
    )
    confidence: UnitInterval = Field(
        description="Model confidence for this image's labels and severity.",
    )


class DamageAssessment(ClaimGuardModel):
    """Aggregated visual damage assessment consumed by fraud, policy, and adjudicator."""

    claim_id: UUID = Field(description="Claim this assessment belongs to.")
    overall_severity: SeverityLevel = Field(
        description="Severity after aggregating all photo findings and the intake narrative.",
    )
    severity_score: UnitInterval = Field(
        description="Continuous severity in [0, 1] used by routing thresholds.",
    )
    estimated_repair_low: Money | None = Field(
        default=None,
        description="Lower bound of a heuristic repair range. Null if no photos or no estimate.",
    )
    estimated_repair_high: Money | None = Field(
        default=None,
        description="Upper bound of a heuristic repair range.",
    )
    photo_findings: list[PhotoFinding] = Field(
        default_factory=list,
        description="Per-image results. Empty when the claim was submitted without photos.",
    )
    narrative: str = Field(
        description="Short visual summary an adjuster can scan. Must not invent unseen damage.",
    )
    inconsistencies: list[str] = Field(
        default_factory=list,
        description="Photo-vs-narrative or photo-vs-photo conflicts (fraud-relevant).",
    )
    model_name: str = Field(
        description="Hugging Face (or other) model id used for classification.",
    )
    model_version: str = Field(
        description="Pinned revision or digest so eval runs are reproducible.",
    )
    confidence: UnitInterval = Field(
        description="Overall confidence, typically the min or calibrated mean of photo confidences.",
    )
