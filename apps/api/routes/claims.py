"""Claim HTTP API. Enqueue is async; the worker runs the LangGraph pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from claimguard.db.models import AgentTraceRow, Claim
from claimguard.db.repository import (
    create_claim_from_source_dir,
    create_claim_from_uploads,
    list_claims,
)
from claimguard.db.session import session_scope
from claimguard.schemas.common import ClaimStatus
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from apps.worker.tasks import process_claim

router = APIRouter(prefix="/v1/claims", tags=["claims"])
REPO_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_ROOT = REPO_ROOT / "data" / "uploads"
ALLOWED_ROOTS = (
    REPO_ROOT / "data" / "synthetic_claims",
    REPO_ROOT / "data" / "eval_set",
    UPLOADS_ROOT,
)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_DOC_SUFFIXES = {".pdf", ".txt", ".md"}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class ClaimSubmitRequest(BaseModel):
    source_dir: str = Field(
        description="Path to a synthetic claim folder (documents/, notes.txt, images/).",
    )


class ClaimSubmitResponse(BaseModel):
    claim_id: UUID
    status: ClaimStatus
    message: str = Field(
        description="Human-readable acknowledgement. Processing is asynchronous.",
    )


class ClaimListItem(BaseModel):
    claim_id: UUID
    status: str
    policy_number: str
    incident_type: str | None = None
    created_at: str | None = None


class ClaimDetail(BaseModel):
    claim_id: UUID
    status: str
    policy_number: str
    incident_type: str | None = None
    error: str | None = None
    intake: dict | None = None
    verdict: dict | None = None
    trace: list[dict] = Field(default_factory=list)


class SampleClaim(BaseModel):
    claim_id: str
    source_dir: str
    label: str


@router.get("/samples")
def list_sample_claims() -> list[SampleClaim]:
    root = REPO_ROOT / "data" / "synthetic_claims"
    samples: list[SampleClaim] = []
    if not root.is_dir():
        return samples
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder / "documents").is_dir():
            continue
        label = folder.name
        claim_json = folder / "claim.json"
        if claim_json.is_file():
            raw = json.loads(claim_json.read_text(encoding="utf-8"))
            incident = raw.get("incident_type")
            if not incident and isinstance(raw.get("incident"), dict):
                incident = raw["incident"].get("incident_type")
            policy = raw.get("policy_number") or folder.name
            peril = raw.get("peril")
            label = " · ".join(part for part in (str(policy), str(peril or incident or "claim")) if part)
        samples.append(
            SampleClaim(
                claim_id=folder.name,
                source_dir=str(folder.relative_to(REPO_ROOT)),
                label=label,
            )
        )
    return samples


@router.get("")
def list_submitted_claims(limit: int = 50) -> list[ClaimListItem]:
    with session_scope() as session:
        rows = list_claims(session, limit=min(max(limit, 1), 200))
        return [
            ClaimListItem(
                claim_id=row.id,
                status=row.status,
                policy_number=row.policy_number,
                incident_type=row.incident_type,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def submit_claim(body: ClaimSubmitRequest) -> ClaimSubmitResponse:
    source = _resolve_source_dir(body.source_dir)
    with session_scope() as session:
        claim = create_claim_from_source_dir(session, source)
        claim_id = claim.id
        claim_status = claim.status
    process_claim.delay(str(claim_id))
    return ClaimSubmitResponse(
        claim_id=claim_id,
        status=ClaimStatus(claim_status),
        message="Claim accepted. Poll GET /v1/claims/{id} for verdict and trace.",
    )


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_claim(
    files: Annotated[list[UploadFile] | None, File()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> ClaimSubmitResponse:
    uploads = files or []
    if not uploads and not (notes and notes.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload at least one document/image or include notes.",
        )
    documents: list[tuple[str, bytes]] = []
    images: list[tuple[str, bytes]] = []
    for upload in uploads:
        filename = _safe_filename(upload.filename or "upload.bin")
        payload = await upload.read()
        if len(payload) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{filename} exceeds the 8MB upload limit.",
            )
        suffix = Path(filename).suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            images.append((filename, payload))
        elif suffix in _DOC_SUFFIXES or suffix == "":
            documents.append((filename, payload))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {filename}",
            )
    dest = UPLOADS_ROOT / str(uuid4())
    with session_scope() as session:
        claim = create_claim_from_uploads(
            session,
            dest,
            documents=documents,
            images=images,
            notes=notes,
        )
        claim_id = claim.id
        claim_status = claim.status
    process_claim.delay(str(claim_id))
    return ClaimSubmitResponse(
        claim_id=claim_id,
        status=ClaimStatus(claim_status),
        message="Claim accepted. Poll GET /v1/claims/{id} for verdict and trace.",
    )


@router.get("/{claim_id}")
def get_claim(claim_id: UUID) -> ClaimDetail:
    return _load_detail(claim_id)


@router.get("/{claim_id}/trace")
def get_claim_trace(claim_id: UUID) -> dict:
    detail = _load_detail(claim_id)
    return {"claim_id": str(claim_id), "status": detail.status, "trace": detail.trace}


@router.get("/{claim_id}/verdict")
def get_claim_verdict(claim_id: UUID) -> dict:
    detail = _load_detail(claim_id)
    if detail.verdict is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Verdict is not ready (status={detail.status}).",
        )
    return {"claim_id": str(claim_id), "status": detail.status, "verdict": detail.verdict}


def _load_detail(claim_id: UUID) -> ClaimDetail:
    with session_scope() as session:
        claim = session.get(Claim, claim_id)
        if claim is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
        traces = (
            session.query(AgentTraceRow)
            .filter(AgentTraceRow.claim_id == claim_id)
            .order_by(AgentTraceRow.created_at.asc())
            .all()
        )
        return ClaimDetail(
            claim_id=claim.id,
            status=claim.status,
            policy_number=claim.policy_number,
            incident_type=claim.incident_type,
            error=claim.error,
            intake=claim.intake,
            verdict=claim.verdict,
            trace=[
                {
                    "agent": row.agent_name,
                    "status": row.status,
                    "prompt_version": row.prompt_version,
                    "model": row.model,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "cost_usd": str(row.cost_usd),
                    "latency_ms": row.latency_ms,
                    "input": row.input_redacted,
                    "output": row.output_json,
                }
                for row in traces
            ],
        )


def _resolve_source_dir(raw: str) -> Path:
    path = Path(raw)
    path = (REPO_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_dir does not exist.")
    if not any(_is_relative_to(path, root.resolve()) for root in ALLOWED_ROOTS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_dir must be under data/synthetic_claims, data/eval_set, or data/uploads.",
        )
    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", Path(name).name).strip("._")
    return cleaned or "upload.bin"
