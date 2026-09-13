"""LangGraph state contract. Every node reads/writes this object, never free text."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from claimguard.schemas.common import ClaimGuardModel
from claimguard.schemas.damage import DamageAssessment
from claimguard.schemas.fraud import FraudSignal
from claimguard.schemas.intake import ClaimIntake
from claimguard.schemas.policy import PolicyDetermination
from claimguard.schemas.trace import AgentTrace
from claimguard.schemas.verdict import TriageVerdict


class GraphError(ClaimGuardModel):
    """A recoverable or terminal error recorded on the state instead of raising blindly."""

    agent: str = Field(description="Node that failed.")
    message: str = Field(description="Redacted error message safe to persist.")
    recoverable: bool = Field(
        description="If true, the graph may skip or retry; if false, the claim is marked failed.",
    )


class GraphState(ClaimGuardModel):
    """Shared state for the claim pipeline StateGraph.

    Conditional edges inspect `errors`, `intake.intake_confidence`,
    `fraud.fraud_risk_score`, and `verdict.overall_confidence`.
    """

    claim_id: UUID = Field(description="Claim being processed.")
    raw_payload: dict[str, Any] | None = Field(
        default=None,
        description="Original enqueue payload (storage URIs, not file bytes).",
    )
    intake: ClaimIntake | None = Field(
        default=None,
        description="Set by the intake node. Required before vision / fraud / policy.",
    )
    damage: DamageAssessment | None = Field(
        default=None,
        description="Set by the vision node. May stay None when there are no photos.",
    )
    fraud: FraudSignal | None = Field(default=None, description="Set by the fraud node.")
    policy: PolicyDetermination | None = Field(
        default=None,
        description="Set by the policy node.",
    )
    verdict: TriageVerdict | None = Field(
        default=None,
        description="Set by the adjudicator node.",
    )
    trace: AgentTrace | None = Field(
        default=None,
        description="Accumulated spans. Updated after every node.",
    )
    errors: list[GraphError] = Field(
        default_factory=list,
        description="Node-level errors collected so the adjudicator can still produce a review verdict.",
    )
    skip_vision: bool = Field(
        default=False,
        description="Set when intake found no images; the graph short-circuits vision.",
    )
