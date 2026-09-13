"""Pydantic contracts used at every agent and API boundary."""

from claimguard.schemas.common import (
    AgentName,
    ClaimGuardModel,
    ClaimStatus,
    CoverageStatus,
    CurrencyCode,
    DamageType,
    DocumentType,
    GeoLocation,
    IncidentType,
    Money,
    RetrievalSource,
    RiskTier,
    RoutingDecision,
    SeverityLevel,
)
from claimguard.schemas.damage import DamageAssessment, DetectedObject, PhotoFinding
from claimguard.schemas.fraud import (
    EntityGraphMatch,
    FraudRuleHit,
    FraudSignal,
    SimilarFraudCase,
)
from claimguard.schemas.graph import GraphError, GraphState
from claimguard.schemas.intake import (
    ClaimantProfile,
    ClaimDocumentRef,
    ClaimImageRef,
    ClaimIntake,
    ExtractedEntity,
    IncidentDetails,
    VehicleInfo,
)
from claimguard.schemas.policy import CitedClause, PolicyDetermination
from claimguard.schemas.trace import AgentSpan, AgentTrace
from claimguard.schemas.verdict import MissingDocument, SettlementMemo, TriageVerdict

__all__ = [
    "AgentName",
    "AgentSpan",
    "AgentTrace",
    "CitedClause",
    "ClaimDocumentRef",
    "ClaimGuardModel",
    "ClaimImageRef",
    "ClaimIntake",
    "ClaimStatus",
    "ClaimantProfile",
    "CoverageStatus",
    "CurrencyCode",
    "DamageAssessment",
    "DamageType",
    "DetectedObject",
    "DocumentType",
    "EntityGraphMatch",
    "ExtractedEntity",
    "FraudRuleHit",
    "FraudSignal",
    "GeoLocation",
    "GraphError",
    "GraphState",
    "IncidentDetails",
    "IncidentType",
    "MissingDocument",
    "Money",
    "PhotoFinding",
    "PolicyDetermination",
    "RetrievalSource",
    "RiskTier",
    "RoutingDecision",
    "SettlementMemo",
    "SeverityLevel",
    "SimilarFraudCase",
    "TriageVerdict",
    "VehicleInfo",
]
