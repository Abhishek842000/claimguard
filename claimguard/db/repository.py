"""Persist claims, artifacts, verdicts, and redacted agent traces."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from claimguard.agents.intake_agent import intake_input_from_claim_dir
from claimguard.db.models import AgentTraceRow, Claim, ClaimDocument, ClaimImage
from claimguard.observability.cost_tracker import CostSummary, TokenUsage, summarize
from claimguard.observability.pii_redaction import redact_mapping, redact_pii
from claimguard.schemas.common import ClaimStatus
from claimguard.schemas.graph import ClaimState, DocumentRef, ImageRef, empty_claim_state


def create_claim_from_source_dir(session: Session, source_dir: Path) -> Claim:
    payload = intake_input_from_claim_dir(source_dir)
    # Always mint a new id so the same sample folder can be submitted more than once.
    claim_id = uuid4()
    policy_number = "UNKNOWN"
    claim_json = source_dir / "claim.json"
    if claim_json.is_file():
        import json

        raw = json.loads(claim_json.read_text(encoding="utf-8"))
        policy_number = str(raw.get("policy_number") or "UNKNOWN")
    claim = Claim(
        id=claim_id,
        status=ClaimStatus.RECEIVED.value,
        policy_number=policy_number,
    )
    session.add(claim)
    session.flush()
    for ref in payload.raw_documents:
        session.add(
            ClaimDocument(
                id=uuid4(),
                claim_id=claim.id,
                filename=ref.filename,
                content_type="application/pdf" if ref.filename.endswith(".pdf") else "text/plain",
                document_type=str(ref.document_type) if ref.document_type else None,
                storage_uri=ref.storage_uri,
            )
        )
    for ref in payload.raw_images:
        session.add(
            ClaimImage(
                id=uuid4(),
                claim_id=claim.id,
                filename=ref.filename,
                content_type="image/jpeg",
                storage_uri=ref.storage_uri,
                caption=ref.caption,
            )
        )
    session.flush()
    return claim


def load_claim_state(session: Session, claim_id: UUID) -> ClaimState:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise KeyError(claim_id)
    documents = [
        DocumentRef(
            document_id=str(doc.id),
            filename=doc.filename,
            storage_uri=doc.storage_uri,
        )
        for doc in claim.documents
    ]
    images = [
        ImageRef(
            image_id=str(image.id),
            filename=image.filename,
            storage_uri=image.storage_uri,
            caption=image.caption,
        )
        for image in claim.images
    ]
    return empty_claim_state(str(claim.id), raw_documents=documents, raw_images=images)


def persist_pipeline_result(session: Session, claim_id: UUID, state: ClaimState) -> Claim:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise KeyError(claim_id)
    if state.get("intake") is not None:
        claim.intake = redact_mapping(state["intake"].model_dump(mode="json"))
        claim.policy_number = state["intake"].policy_number
        claim.incident_type = str(state["intake"].incident.incident_type)
        claim.claimed_amount = state["intake"].claimed_amount.amount
    if state.get("verdict") is not None:
        claim.verdict = state["verdict"].model_dump(mode="json")
    if state.get("error"):
        claim.error = redact_pii(state["error"])
    if state.get("requires_human_review") or state.get("error"):
        claim.status = ClaimStatus.NEEDS_REVIEW.value
    elif state.get("verdict") is not None:
        claim.status = ClaimStatus.AUTO_RESOLVED.value
    else:
        claim.status = ClaimStatus.FAILED.value

    session.query(AgentTraceRow).filter(AgentTraceRow.claim_id == claim_id).delete()
    for step in state.get("trace") or []:
        session.add(
            AgentTraceRow(
                claim_id=claim_id,
                trace_id=str(claim_id),
                agent_name=step.agent[:32],
                span_id=uuid4().hex,
                prompt_version=step.prompt_version,
                model=step.model,
                input_redacted=redact_mapping(step.input_snapshot),
                output_json=redact_mapping(step.output_snapshot),
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
                cost_usd=step.cost_usd or Decimal("0"),
                latency_ms=step.latency_ms,
                status=step.status,
            )
        )
    session.flush()
    return claim


def list_claims(session: Session, *, limit: int = 50) -> list[Claim]:
    return (
        session.query(Claim)
        .order_by(Claim.created_at.desc())
        .limit(limit)
        .all()
    )


def create_claim_from_uploads(
    session: Session,
    dest: Path,
    *,
    documents: list[tuple[str, bytes]],
    images: list[tuple[str, bytes]],
    notes: str | None,
) -> Claim:
    """Write uploaded bytes into a claim folder, then reuse the source_dir path."""
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "documents").mkdir(exist_ok=True)
    (dest / "images").mkdir(exist_ok=True)
    for filename, payload in documents:
        (dest / "documents" / filename).write_bytes(payload)
    for filename, payload in images:
        (dest / "images" / filename).write_bytes(payload)
    if notes:
        (dest / "notes.txt").write_text(notes, encoding="utf-8")
    return create_claim_from_source_dir(session, dest)


def fetch_cost_metrics(session: Session) -> CostSummary:
    """Roll up persisted traces. API and worker do not share memory."""
    rows = session.query(
        AgentTraceRow.claim_id,
        AgentTraceRow.agent_name,
        AgentTraceRow.model,
        AgentTraceRow.input_tokens,
        AgentTraceRow.output_tokens,
        AgentTraceRow.cost_usd,
    ).all()
    usages = [
        TokenUsage(
            agent=row.agent_name,
            model=row.model or "unknown",
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cost_usd=row.cost_usd or Decimal("0"),
            claim_id=str(row.claim_id),
        )
        for row in rows
    ]
    if usages:
        return summarize(usages)
    claim_count = session.query(func.count(Claim.id)).scalar() or 0
    return CostSummary(
        total_cost_usd=Decimal("0"),
        claim_count=int(claim_count),
        average_cost_per_claim=Decimal("0"),
        by_agent=[],
    )


def mark_processing(session: Session, claim_id: UUID) -> None:
    claim = session.get(Claim, claim_id)
    if claim is not None:
        claim.status = ClaimStatus.PROCESSING.value
        session.flush()
