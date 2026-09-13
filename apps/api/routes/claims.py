"""Claim HTTP API. Enqueue is async; the worker runs the LangGraph pipeline."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from claimguard.db.models import AgentTraceRow, Claim
from claimguard.db.repository import create_claim_from_source_dir
from claimguard.db.session import session_scope
from claimguard.schemas.common import ClaimStatus
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from apps.worker.tasks import process_claim

router = APIRouter(prefix="/v1/claims", tags=["claims"])
REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_ROOTS = (REPO_ROOT / "data" / "synthetic_claims", REPO_ROOT / "data" / "eval_set")


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


class ClaimDetail(BaseModel):
    claim_id: UUID
    status: str
    policy_number: str
    incident_type: str | None = None
    error: str | None = None
    intake: dict | None = None
    verdict: dict | None = None
    trace: list[dict] = Field(default_factory=list)


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
            detail="source_dir must be under data/synthetic_claims or data/eval_set.",
        )
    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
