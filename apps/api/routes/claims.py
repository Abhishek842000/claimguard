"""Claim HTTP API. Handlers are stubs until Phase 1 wires intake + the queue."""

from uuid import UUID

from claimguard.schemas.common import ClaimStatus
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/claims", tags=["claims"])


class ClaimSubmitResponse(BaseModel):
    claim_id: UUID
    status: ClaimStatus
    message: str = Field(
        description="Human-readable acknowledgement. Processing is asynchronous.",
    )


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def submit_claim() -> ClaimSubmitResponse:
    """Enqueue a claim for the LangGraph worker. Implemented in Phase 1."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Claim submission is implemented in Phase 1.",
    )


@router.get("/{claim_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_claim(claim_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Claim status is implemented in Phase 1.",
    )


@router.get("/{claim_id}/trace", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_claim_trace(claim_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Agent traces are implemented in Phase 1.",
    )


@router.get("/{claim_id}/verdict", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_claim_verdict(claim_id: UUID) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Verdicts are implemented in Phase 1.",
    )
