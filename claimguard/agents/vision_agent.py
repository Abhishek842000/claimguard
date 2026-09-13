"""Vision agent — damage classification / severity from claim photos."""

from __future__ import annotations

from uuid import UUID

from claimguard.intake.pdf_parser import resolve_storage_uri
from claimguard.schemas.common import SeverityLevel
from claimguard.schemas.damage import DamageAssessment, PhotoFinding
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate, ImageRef
from claimguard.vision.damage_classifier import DamageClassifier, HeuristicDamageClassifier

_SEVERITY_SCORE = {
    SeverityLevel.MINIMAL: 0.1,
    SeverityLevel.LOW: 0.25,
    SeverityLevel.MODERATE: 0.5,
    SeverityLevel.HIGH: 0.75,
    SeverityLevel.CATASTROPHIC: 0.95,
}


def run_vision_agent(
    state: ClaimState,
    *,
    classifier: DamageClassifier | None = None,
) -> ClaimStateUpdate:
    backend = classifier or HeuristicDamageClassifier()
    images = _images(state)
    context = _claim_context(state)
    findings: list[PhotoFinding] = []
    for image in images:
        findings.append(
            backend.classify(
                resolve_storage_uri(image.storage_uri),
                image_id=_as_uuid(image.image_id),
                caption=image.caption,
                context=context,
            )
        )
    if not findings:
        assessment = DamageAssessment(
            claim_id=_as_uuid(state["claim_id"]),
            overall_severity=SeverityLevel.LOW,
            severity_score=0.2,
            photo_findings=[],
            narrative="No damage photos were attached.",
            model_name=backend.name,
            model_version=backend.version,
            confidence=0.4,
        )
        return _ok(assessment, backend)

    worst = max(findings, key=lambda item: _SEVERITY_SCORE[SeverityLevel(item.severity)])
    score = _SEVERITY_SCORE[SeverityLevel(worst.severity)]
    types = sorted({label for finding in findings for label in finding.damage_types})
    assessment = DamageAssessment(
        claim_id=_as_uuid(state["claim_id"]),
        overall_severity=SeverityLevel(worst.severity),
        severity_score=score,
        photo_findings=findings,
        narrative=(
            f"{len(findings)} photo(s). Dominant labels: "
            + ", ".join(str(label) for label in types)
        ),
        model_name=backend.name,
        model_version=backend.version,
        confidence=min(finding.confidence for finding in findings),
    )
    return _ok(assessment, backend)


def _ok(assessment: DamageAssessment, backend: DamageClassifier) -> ClaimStateUpdate:
    return {
        "damage_assessment": assessment,
        "trace": [
            AgentStep.completed(
                "vision_agent",
                output_schema="DamageAssessment",
                model=backend.name,
                prompt_version=None,
                output_snapshot=assessment.model_dump(mode="json"),
                metadata={"classifier": backend.name, "version": backend.version},
            )
        ],
    }


def _claim_context(state: ClaimState) -> str:
    """Filename-only heuristics fail on `demo_img.webp`; notes still name the peril."""
    intake = state.get("intake")
    if intake is None:
        return ""
    return " ".join(
        part
        for part in (
            intake.adjuster_notes,
            intake.incident.description,
            str(intake.incident.incident_type),
        )
        if part
    )


def _images(state: ClaimState) -> list[ImageRef]:
    intake = state.get("intake")
    if intake is not None and intake.images:
        return [
            ImageRef(
                image_id=str(image.image_id),
                filename=image.filename,
                storage_uri=image.storage_uri,
                caption=image.caption,
            )
            for image in intake.images
        ]
    return list(state.get("raw_images") or [])


def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
