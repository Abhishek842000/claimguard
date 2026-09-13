"""Schemas produced by the policy agent (hybrid RAG over policy documents)."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from claimguard.schemas.common import (
    ClaimGuardModel,
    CoverageStatus,
    Money,
    RetrievalSource,
    UnitInterval,
)


class CitedClause(ClaimGuardModel):
    """A verbatim policy passage the coverage decision depends on."""

    document_id: str = Field(description="Policy document id in the policy corpus.")
    document_title: str = Field(
        description="Display title, e.g. 'Personal Auto Policy PP 00 01 09 18'.",
    )
    clause_id: str = Field(
        description="Stable clause / chunk id used for groundedness scoring.",
    )
    section: str = Field(
        description="Section heading, e.g. 'Part D — Coverage For Damage To Your Auto'.",
    )
    quote: str = Field(
        description="Verbatim quote from the retrieved chunk. Do not paraphrase here.",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="1-based page number when the source PDF has page metadata.",
    )
    relevance: UnitInterval = Field(
        description="Reranker score for this clause against the claim query.",
    )
    source: RetrievalSource = Field(
        default=RetrievalSource.RERANK,
        description="Retrieval stage that selected this clause for the prompt.",
    )


class PolicyDetermination(ClaimGuardModel):
    """Coverage decision with cited clauses. Null payout fields when excluded or unknown."""

    claim_id: UUID = Field(description="Claim this determination belongs to.")
    coverage_status: CoverageStatus = Field(
        description="Covered, partial, excluded, or not enough information to decide.",
    )
    covered_perils: list[str] = Field(
        default_factory=list,
        description="Perils the cited clauses actually insure for this incident type.",
    )
    supporting_clauses: list[CitedClause] = Field(
        default_factory=list,
        description="Clauses that support coverage or partial coverage.",
    )
    exclusions_applied: list[CitedClause] = Field(
        default_factory=list,
        description="Exclusion / condition clauses that limit or deny coverage.",
    )
    deductible: Money | None = Field(
        default=None,
        description="Applicable deductible when a declarations-like fact was retrieved or supplied.",
    )
    coverage_limit: Money | None = Field(
        default=None,
        description="Applicable limit of liability when known.",
    )
    estimated_payable: Money | None = Field(
        default=None,
        description="Preliminary payable estimate (claimed minus deductible, capped by limit).",
    )
    rationale: str = Field(
        description=(
            "Adjuster-facing explanation. Every material claim must map to a cited clause_id; "
            "ungrounded statements are counted as hallucinations in eval."
        ),
    )
    information_gaps: list[str] = Field(
        default_factory=list,
        description="Facts still needed to finish the coverage analysis.",
    )
    retrieved_chunk_ids: list[str] = Field(
        default_factory=list,
        description="All policy_chunks ids considered, including unused ones.",
    )
    grounded: bool = Field(
        default=True,
        description="False when a grounding check found uncited assertions.",
    )
    confidence: UnitInterval = Field(
        description="Confidence in the coverage_status label, not in the payout math.",
    )
