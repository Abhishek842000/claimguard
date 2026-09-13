"""Shared value objects and enumerations used across agent boundaries."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ClaimGuardModel(BaseModel):
    """Strict base model: extra fields are rejected so agent contracts stay explicit."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )


class IncidentType(StrEnum):
    """High-level peril that drives policy lookup and required-document rules."""

    AUTO_COLLISION = "auto_collision"
    AUTO_THEFT = "auto_theft"
    AUTO_VANDALISM = "auto_vandalism"
    AUTO_WEATHER = "auto_weather"
    PROPERTY_WATER = "property_water"
    PROPERTY_FIRE = "property_fire"
    PROPERTY_THEFT = "property_theft"
    PROPERTY_WEATHER = "property_weather"
    LIABILITY = "liability"
    OTHER = "other"


class ClaimStatus(StrEnum):
    """Lifecycle of a claim inside ClaimGuard, independent of the carrier's LOS."""

    RECEIVED = "received"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    AUTO_RESOLVED = "auto_resolved"
    FAILED = "failed"


class DocumentType(StrEnum):
    """Document classes the intake agent is expected to recognize."""

    CLAIM_FORM = "claim_form"
    POLICE_REPORT = "police_report"
    ESTIMATE = "estimate"
    MEDICAL_BILL = "medical_bill"
    PROOF_OF_LOSS = "proof_of_loss"
    DECLARATIONS_PAGE = "declarations_page"
    CORRESPONDENCE = "correspondence"
    ADJUSTER_NOTE = "adjuster_note"
    OTHER = "other"


class DamageType(StrEnum):
    """Labels produced by the vision classifier (plus a catch-all)."""

    DENT = "dent"
    SCRATCH = "scratch"
    CRACKED_GLASS = "cracked_glass"
    BROKEN_LIGHT = "broken_light"
    DEPLOYED_AIRBAG = "deployed_airbag"
    STRUCTURAL = "structural"
    WATER_STAIN = "water_stain"
    FIRE_CHAR = "fire_char"
    THEFT_ENTRY = "theft_entry"
    NONE_VISIBLE = "none_visible"
    UNKNOWN = "unknown"


class SeverityLevel(StrEnum):
    """Ordinal damage / loss severity used for routing thresholds."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CATASTROPHIC = "catastrophic"


class CoverageStatus(StrEnum):
    """Policy agent's coverage determination."""

    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    EXCLUDED = "excluded"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class RoutingDecision(StrEnum):
    """Adjudicator routing. Auto-resolve is only allowed under policy thresholds."""

    AUTO_RESOLVE = "auto_resolve"
    HUMAN_REVIEW = "human_review"


class RetrievalSource(StrEnum):
    """Which retriever produced a cited chunk, before / after fusion and rerank."""

    BM25 = "bm25"
    DENSE = "dense"
    RRF = "rrf"
    RERANK = "rerank"


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentName(StrEnum):
    INTAKE = "intake"
    VISION = "vision"
    FRAUD = "fraud"
    POLICY = "policy"
    ADJUDICATOR = "adjudicator"


class CurrencyCode(StrEnum):
    USD = "USD"


NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
]
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]


class Money(ClaimGuardModel):
    """Currency amount. Serialized as a decimal string to avoid float rounding."""

    amount: NonNegativeDecimal = Field(
        description="Numeric amount in major currency units (e.g. 1425.50 dollars).",
    )
    currency: CurrencyCode = Field(
        default=CurrencyCode.USD,
        description="ISO-4217 currency code. Phase 0 corpus is USD-only.",
    )


class GeoLocation(ClaimGuardModel):
    """Coarse incident location. Street-level address is treated as PII."""

    city: str = Field(description="City where the loss occurred.")
    state: str = Field(
        min_length=2,
        max_length=2,
        description="Two-letter US state / territory code.",
    )
    postal_code: str | None = Field(
        default=None,
        description="ZIP or ZIP+4. PII — redact before logging.",
    )
    street_address: str | None = Field(
        default=None,
        description="Street address if present on the claim form. PII — redact before logging.",
    )
