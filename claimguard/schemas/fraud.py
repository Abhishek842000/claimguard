"""Schemas produced by the fraud agent (hybrid RAG + rule / entity-graph signals)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from claimguard.schemas.common import (
    ClaimGuardModel,
    RetrievalSource,
    RiskTier,
    UnitInterval,
)


class FraudRuleHit(ClaimGuardModel):
    """A deterministic rule that fired. Rules are versioned separately from LLM prompts."""

    rule_id: str = Field(description="Stable id, e.g. 'FR-LATE-REPORT-30D'.")
    rule_name: str = Field(description="Human-readable rule name.")
    severity: Literal["low", "medium", "high"] = Field(
        description="How strongly this single rule should move the risk score.",
    )
    detail: str = Field(
        description="Why the rule fired on this claim, citing the intake field values used.",
    )
    rule_version: str = Field(
        default="v1",
        description="Rule-pack version so eval can slice by ruleset.",
    )


class SimilarFraudCase(ClaimGuardModel):
    """A retrieved historical fraud pattern or labeled case used as evidence."""

    case_id: str = Field(description="Id in the fraud corpus (chunk or case key).")
    similarity: UnitInterval = Field(
        description="Retriever / reranker score normalized to [0, 1] when possible.",
    )
    source: RetrievalSource = Field(
        description="Which stage of hybrid retrieval surfaced this case.",
    )
    excerpt: str = Field(
        description="Quoted passage from the corpus. Must be used verbatim in justifications.",
    )
    citation: str = Field(
        description="Human-readable citation, e.g. 'NICB pattern bulletin 2022-04 §3'.",
    )


class EntityGraphMatch(ClaimGuardModel):
    """Shared-entity hit across claims (same VIN, address, phone, repair shop, etc.)."""

    entity_type: str = Field(description="VIN, PHONE, ADDRESS, SHOP, POLICY_NUMBER, ...")
    entity_value_redacted: str = Field(
        description="Masked value safe to log and display, e.g. 'VIN ****XYZ12'.",
    )
    matched_claim_ids: list[str] = Field(
        description="Other claim ids (synthetic) that share this entity.",
    )
    relationship: str = Field(
        description="Edge label such as same_vin, same_address, shared_repair_shop.",
    )


class FraudSignal(ClaimGuardModel):
    """Fraud agent's structured output. Justification must be grounded in hits + cases."""

    claim_id: UUID = Field(description="Claim this signal belongs to.")
    fraud_risk_score: UnitInterval = Field(
        description="Calibrated risk in [0, 1]. Thresholds for routing live in the adjudicator.",
    )
    risk_tier: RiskTier = Field(
        description="Bucketed risk for UI and eval slices (low / medium / high).",
    )
    rule_hits: list[FraudRuleHit] = Field(
        default_factory=list,
        description="Deterministic signals. An empty list is a valid 'no rules fired' result.",
    )
    similar_cases: list[SimilarFraudCase] = Field(
        default_factory=list,
        description="Top reranked corpus neighbors. Empty if retrieval returned nothing.",
    )
    entity_matches: list[EntityGraphMatch] = Field(
        default_factory=list,
        description="Cross-claim entity graph matches, values already redacted.",
    )
    justification: str = Field(
        description=(
            "Narrative an adjuster can audit. Must cite rule_ids and case_ids; "
            "must not invent corpus evidence that is not in similar_cases."
        ),
    )
    retrieved_chunk_ids: list[str] = Field(
        default_factory=list,
        description="All fraud_case_chunks ids considered, including those not cited.",
    )
    grounded: bool = Field(
        default=True,
        description="False when the model produced claims that failed the grounding check.",
    )
    confidence: UnitInterval = Field(
        description="Model + retriever confidence, distinct from the risk score itself.",
    )
