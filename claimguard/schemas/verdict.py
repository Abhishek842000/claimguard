"""Final adjudicator output: scores, checklist, memo, and routing decision."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, model_validator

from claimguard.schemas.common import (
    ClaimGuardModel,
    DocumentType,
    Money,
    RoutingDecision,
    UnitInterval,
)
from claimguard.schemas.policy import PolicyDetermination


class MissingDocument(ClaimGuardModel):
    """A document the adjudicator still needs before auto-resolve is responsible."""

    document_type: DocumentType = Field(description="What is missing.")
    reason: str = Field(description="Why this document is required for this claim.")
    required_for: str = Field(
        description="One of coverage | fraud | settlement | compliance.",
    )
    blocking: bool = Field(
        default=True,
        description="If true, missing this document forces human review.",
    )


class SettlementMemo(ClaimGuardModel):
    """Draft memo. A draft is always produced; it is not authorization to pay."""

    summary: str = Field(
        description="One-paragraph synopsis of incident, coverage, and recommended next step.",
    )
    recommended_payout: Money | None = Field(
        default=None,
        description="Suggested payout when coverage is at least partial and fraud risk is low.",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that must hold before payment (e.g. receive salvage title).",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Limitations of the automated analysis the human reviewer should know.",
    )


class TriageVerdict(ClaimGuardModel):
    """What the API and UI persist as the claim's decision record."""

    claim_id: UUID = Field(description="Claim this verdict belongs to.")
    severity_score: UnitInterval = Field(
        description="Final severity in [0, 1], usually taken from DamageAssessment.severity_score.",
    )
    fraud_risk_score: UnitInterval = Field(
        description="Final fraud risk in [0, 1], usually taken from FraudSignal.fraud_risk_score.",
    )
    coverage: PolicyDetermination = Field(
        description="Embedded policy determination so the verdict is self-contained.",
    )
    missing_documents: list[MissingDocument] = Field(
        default_factory=list,
        description="Checklist shown in the UI and used as a routing signal.",
    )
    settlement_memo: SettlementMemo = Field(
        description="Draft settlement / denial memo for the reviewer.",
    )
    routing: RoutingDecision = Field(
        description="auto_resolve or human_review. See routing_reasons for the why.",
    )
    routing_reasons: list[str] = Field(
        description="Ordered reasons that produced the routing decision (threshold hits, gaps).",
    )
    overall_confidence: UnitInterval = Field(
        description="Min (or calibrated combination) of sub-agent confidences.",
    )
    human_review_required: bool = Field(
        description="Convenience mirror of routing == human_review.",
    )
    prompt_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Prompt name → version used by each agent, e.g. {'fraud': 'fraud_v1'}.",
    )
    model_routing: dict[str, str] = Field(
        default_factory=dict,
        description="Agent name → model id actually called (cheap vs frontier).",
    )

    @model_validator(mode="after")
    def routing_matches_flag(self) -> TriageVerdict:
        expected = self.routing == RoutingDecision.HUMAN_REVIEW
        if self.human_review_required != expected:
            raise ValueError(
                "human_review_required must be True iff routing is human_review"
            )
        return self
