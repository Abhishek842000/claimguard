"""Intake agent — parse PDFs/notes into `ClaimIntake` via structured extraction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from claimguard.intake.heuristic import HeuristicIntakeCompleter
from claimguard.intake.ner import EntityExtractor, RegexEntityExtractor
from claimguard.intake.ocr import OcrBackend
from claimguard.intake.pdf_parser import ParsedDocument, parse_document
from claimguard.llm.prompts import load_prompt
from claimguard.llm.structured_output import Completer, generate_structured
from claimguard.schemas.common import DocumentType, Money
from claimguard.schemas.graph import (
    AgentStep,
    ClaimState,
    ClaimStateUpdate,
    DocumentRef,
    ImageRef,
    IntakeAgentInput,
)
from claimguard.schemas.intake import (
    ClaimDocumentRef,
    ClaimImageRef,
    ClaimIntake,
    ExtractedEntity,
    IntakeExtraction,
)

_UUID_NS = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # NAMESPACE_URL


def run_intake_agent(
    state: ClaimState,
    *,
    completer: Completer | None = None,
    ocr: OcrBackend | None = None,
    ner: EntityExtractor | None = None,
) -> ClaimStateUpdate:
    """LangGraph node. Returns a partial `ClaimState` update."""

    return run_intake(
        IntakeAgentInput(
            claim_id=state["claim_id"],
            raw_documents=list(state.get("raw_documents") or []),
            raw_images=list(state.get("raw_images") or []),
        ),
        completer=completer,
        ocr=ocr,
        ner=ner,
    )


def run_intake(
    payload: IntakeAgentInput,
    *,
    completer: Completer | None = None,
    ocr: OcrBackend | None = None,
    ner: EntityExtractor | None = None,
) -> ClaimStateUpdate:
    parsed = [parse_document(ref, ocr=ocr) for ref in payload.raw_documents]
    notes = payload.notes_text or _notes_from_parsed(parsed)
    document_text = _join_document_text(parsed)
    extractor = ner or RegexEntityExtractor()
    ner_entities = extractor.extract(f"{document_text}\n{notes}")

    prompt = load_prompt("intake_v1")
    user = prompt.render_user(
        claim_id=payload.claim_id,
        document_text=document_text or "(no extractable text)",
        adjuster_notes=notes or "(none)",
        ner_json=json.dumps([e.model_dump(mode="json") for e in ner_entities], indent=2),
    )
    used = completer or HeuristicIntakeCompleter(document_text, notes)
    result = generate_structured(
        user,
        IntakeExtraction,
        completer=used,
        system=prompt.system,
    )

    if not result.ok or result.value is None:
        return {
            "error": (
                f"intake structured output exhausted after {result.attempts} attempt(s): "
                f"{result.errors[-1] if result.errors else 'unknown'}"
            ),
            "requires_human_review": True,
            "trace": [
                AgentStep.completed(
                    "intake_agent",
                    status="error",
                    error="structured output exhausted",
                    metadata={
                        "attempts": result.attempts,
                        "prompt": prompt.name,
                        "prompt_version": prompt.version,
                    },
                )
            ],
        }

    intake = assemble_claim_intake(
        payload,
        result.value,
        parsed=parsed,
        ner_entities=ner_entities,
        notes=notes,
        parser_versions={
            "prompt": f"{prompt.name}:{prompt.version}",
            "ner": extractor.name,
            "pdf": "pypdf",
            **{f"doc:{doc.filename}": doc.method for doc in parsed},
        },
    )
    return {
        "intake": intake,
        "trace": [
            AgentStep.completed(
                "intake_agent",
                output_schema="ClaimIntake",
                metadata={
                    "attempts": result.attempts,
                    "prompt": prompt.name,
                    "prompt_version": prompt.version,
                    "parse_methods": [doc.method for doc in parsed],
                },
            )
        ],
    }


def assemble_claim_intake(
    payload: IntakeAgentInput,
    extraction: IntakeExtraction,
    *,
    parsed: list[ParsedDocument],
    ner_entities: list[ExtractedEntity],
    notes: str,
    parser_versions: dict[str, str],
) -> ClaimIntake:
    missing = list(extraction.missing_fields)
    policy = (extraction.policy_number or "").strip()
    if not policy:
        policy = "UNKNOWN"
        if "policy_number" not in missing:
            missing.append("policy_number")
    amount = extraction.claimed_amount or Money(amount=Decimal("0"))
    if extraction.claimed_amount is None and "claimed_amount" not in missing:
        missing.append("claimed_amount")

    entities = _merge_entities(ner_entities, extraction.extracted_entities)
    return ClaimIntake(
        claim_id=_as_uuid(payload.claim_id),
        policy_number=policy,
        claimant=extraction.claimant,
        incident=extraction.incident,
        claimed_amount=amount,
        adjuster_notes=notes,
        documents=[_to_document_ref(doc, payload) for doc in parsed],
        images=[_to_image_ref(image) for image in payload.raw_images],
        extracted_entities=entities,
        missing_fields=missing,
        intake_confidence=extraction.intake_confidence,
        parser_versions=parser_versions,
        created_at=datetime.now(UTC),
    )


def intake_input_from_claim_dir(claim_dir: Path) -> IntakeAgentInput:
    """Build intake input from a Phase 1 `data/synthetic_claims/<id>/` folder."""

    claim_dir = claim_dir.resolve()
    claim_id = claim_dir.name
    documents: list[DocumentRef] = []
    for path in sorted((claim_dir / "documents").glob("*")) if (claim_dir / "documents").is_dir() else []:
        documents.append(
            DocumentRef(
                document_id=str(uuid5(_UUID_NS, str(path))),
                filename=path.name,
                storage_uri=path.resolve().as_uri(),
                document_type=DocumentType.CLAIM_FORM if path.suffix.lower() == ".pdf" else None,
            )
        )
    notes_path = claim_dir / "notes.txt"
    notes_text = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else None
    if notes_path.is_file():
        documents.append(
            DocumentRef(
                document_id=str(uuid5(_UUID_NS, str(notes_path))),
                filename=notes_path.name,
                storage_uri=notes_path.resolve().as_uri(),
                document_type=DocumentType.ADJUSTER_NOTE,
            )
        )
    images: list[ImageRef] = []
    images_dir = claim_dir / "images"
    if images_dir.is_dir():
        for path in sorted(images_dir.glob("*")):
            images.append(
                ImageRef(
                    image_id=str(uuid5(_UUID_NS, str(path))),
                    filename=path.name,
                    storage_uri=path.resolve().as_uri(),
                )
            )
    return IntakeAgentInput(
        claim_id=claim_id,
        raw_documents=documents,
        raw_images=images,
        notes_text=notes_text,
    )


def _notes_from_parsed(parsed: list[ParsedDocument]) -> str:
    notes = [doc.text for doc in parsed if "note" in doc.filename.lower() and doc.text.strip()]
    return "\n\n".join(notes)


def _join_document_text(parsed: list[ParsedDocument]) -> str:
    chunks: list[str] = []
    for doc in parsed:
        if "note" in doc.filename.lower():
            continue
        if doc.text.strip():
            chunks.append(f"# {doc.filename}\n{doc.text.strip()}")
    return "\n\n".join(chunks)


def _to_document_ref(doc: ParsedDocument, payload: IntakeAgentInput) -> ClaimDocumentRef:
    declared = next(
        (ref.document_type for ref in payload.raw_documents if ref.document_id == doc.document_id),
        None,
    )
    if declared is None:
        declared = (
            DocumentType.ADJUSTER_NOTE
            if "note" in doc.filename.lower()
            else DocumentType.CLAIM_FORM
        )
    return ClaimDocumentRef(
        document_id=_as_uuid(doc.document_id),
        document_type=declared,
        filename=doc.filename,
        storage_uri=doc.storage_uri,
        page_count=doc.page_count,
        extracted_text_preview=doc.preview or None,
    )


def _to_image_ref(image: ImageRef) -> ClaimImageRef:
    return ClaimImageRef(
        image_id=_as_uuid(image.image_id),
        filename=image.filename,
        storage_uri=image.storage_uri,
        caption=image.caption,
    )


def _merge_entities(
    ner: list[ExtractedEntity], extra: list[ExtractedEntity]
) -> list[ExtractedEntity]:
    seen: set[tuple[str, str]] = set()
    merged: list[ExtractedEntity] = []
    for entity in [*ner, *extra]:
        key = (entity.entity_type, entity.value)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entity)
    return merged


def _as_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        return uuid5(_UUID_NS, value)
