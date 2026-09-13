"""LangGraph state contract. Every node reads/writes this object, never free text.

`ClaimState` is the backbone: a TypedDict so LangGraph can merge partial updates
from parallel nodes. Pydantic models still sit *on* the state (intake, verdict,
…) and remain `extra="forbid"` at those agent boundaries.
"""

from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypedDict

from pydantic import Field

from claimguard.schemas.common import ClaimGuardModel, DocumentType
from claimguard.schemas.damage import DamageAssessment
from claimguard.schemas.fraud import FraudSignal
from claimguard.schemas.intake import ClaimIntake
from claimguard.schemas.policy import PolicyDetermination
from claimguard.schemas.verdict import TriageVerdict


def coalesce_error(left: str | None, right: str | None) -> str | None:
    """Reducer for `error`: keep the first non-empty message if parallel nodes fail."""

    if left:
        return left
    return right


class DocumentRef(ClaimGuardModel):
    """Pointer to a raw non-image artifact the intake agent will parse.

    This is the *pre-intake* storage handle. Parsed text and NER live on
    `ClaimIntake.documents` after the intake node runs.
    """

    document_id: str = Field(description="Stable id for this file (matches claim_documents).")
    filename: str = Field(description="Original upload filename, not a storage path.")
    storage_uri: str = Field(
        description="Internal URI (local volume or object storage) used by the worker.",
    )
    document_type: DocumentType | None = Field(
        default=None,
        description="Declared class if known at enqueue time; intake may overwrite.",
    )
    mime_type: str | None = Field(
        default=None,
        description="MIME type when the uploader or ingest job recorded one.",
    )
    page_count: int | None = Field(
        default=None,
        ge=1,
        description="PDF page count if already known; null for non-paginated files.",
    )


class ImageRef(ClaimGuardModel):
    """Pointer to a raw damage photo the vision agent will classify."""

    image_id: str = Field(description="Stable id for this photo (matches claim_images).")
    filename: str = Field(description="Original upload filename.")
    storage_uri: str = Field(description="Internal URI for the bytes on disk / object storage.")
    caption: str | None = Field(
        default=None,
        description="Optional submitter caption (e.g. 'front bumper, passenger side').",
    )


class AgentStep(ClaimGuardModel):
    """One graph-node visit appended to `ClaimState.trace`.

    Parallel specialists each return their own step list; LangGraph concatenates
    them with `operator.add`. Persisted traces map these onto `AgentSpan`.
    """

    agent: str = Field(
        description="Graph node name, e.g. 'intake_agent' or 'route_to_human'.",
    )
    status: Literal["ok", "error", "skipped"] = Field(
        description="ok on a validated write; skipped if the node no-oped; error on failure.",
    )
    started_at: datetime = Field(description="UTC start time.")
    ended_at: datetime | None = Field(
        default=None,
        description="UTC end time. Null only if the span was interrupted mid-flight.",
    )
    latency_ms: int | None = Field(
        default=None,
        ge=0,
        description="Wall-clock duration in milliseconds.",
    )
    output_schema: str | None = Field(
        default=None,
        description="Pydantic model name written by this step, e.g. 'FraudSignal'.",
    )
    error: str | None = Field(
        default=None,
        description="Redacted error message when status is error.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-PII extras (chunk ids, retry count). Never store raw claimant fields.",
    )

    @classmethod
    def completed(
        cls,
        agent: str,
        *,
        status: Literal["ok", "error", "skipped"] = "ok",
        output_schema: str | None = None,
        error: str | None = None,
        latency_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentStep:
        """Build a finished step with matching start/end timestamps."""

        ended = datetime.now(UTC)
        return cls(
            agent=agent,
            status=status,
            started_at=ended,
            ended_at=ended,
            latency_ms=latency_ms,
            output_schema=output_schema,
            error=error,
            metadata=metadata or {},
        )


class ClaimState(TypedDict):
    """Shared LangGraph state for one claim. This is the pipeline backbone.

    Nodes return a `ClaimStateUpdate` (partial). Parallel specialists write
    disjoint keys (`damage_assessment` / `fraud_signal` / `policy_determination`)
    and append to `trace` via a reducer so last-write-wins cannot drop a step.
    """

    claim_id: str
    raw_documents: list[DocumentRef]
    raw_images: list[ImageRef]
    intake: ClaimIntake | None
    damage_assessment: DamageAssessment | None
    fraud_signal: FraudSignal | None
    policy_determination: PolicyDetermination | None
    verdict: TriageVerdict | None
    trace: Annotated[list[AgentStep], operator.add]
    requires_human_review: bool
    error: Annotated[str | None, coalesce_error]


class ClaimStateUpdate(TypedDict, total=False):
    """Partial write returned by a node. Omitted keys are left unchanged."""

    claim_id: str
    raw_documents: list[DocumentRef]
    raw_images: list[ImageRef]
    intake: ClaimIntake | None
    damage_assessment: DamageAssessment | None
    fraud_signal: FraudSignal | None
    policy_determination: PolicyDetermination | None
    verdict: TriageVerdict | None
    trace: list[AgentStep]
    requires_human_review: bool
    error: str | None


class GraphError(ClaimGuardModel):
    """Structured node failure. The live graph stores a single `error` string;

    keep this model for persistence / UI when a claim records more than one
    recoverable failure.
    """

    agent: str = Field(description="Node that failed.")
    message: str = Field(description="Redacted error message safe to persist.")
    recoverable: bool = Field(
        description="If true, the graph may skip or retry; if false, the claim is marked failed.",
    )


class GraphState(ClaimGuardModel):
    """Validated snapshot of `ClaimState` for tests, persistence, and API dumps.

    LangGraph itself uses the TypedDict. Convert with `to_claim_state()`.
    """

    claim_id: str = Field(description="Claim being processed.")
    raw_documents: list[DocumentRef] = Field(default_factory=list)
    raw_images: list[ImageRef] = Field(default_factory=list)
    intake: ClaimIntake | None = Field(default=None)
    damage_assessment: DamageAssessment | None = Field(default=None)
    fraud_signal: FraudSignal | None = Field(default=None)
    policy_determination: PolicyDetermination | None = Field(default=None)
    verdict: TriageVerdict | None = Field(default=None)
    trace: list[AgentStep] = Field(default_factory=list)
    requires_human_review: bool = Field(default=False)
    error: str | None = Field(default=None)

    def to_claim_state(self) -> ClaimState:
        return {
            "claim_id": self.claim_id,
            "raw_documents": list(self.raw_documents),
            "raw_images": list(self.raw_images),
            "intake": self.intake,
            "damage_assessment": self.damage_assessment,
            "fraud_signal": self.fraud_signal,
            "policy_determination": self.policy_determination,
            "verdict": self.verdict,
            "trace": list(self.trace),
            "requires_human_review": self.requires_human_review,
            "error": self.error,
        }


def empty_claim_state(
    claim_id: str,
    *,
    raw_documents: list[DocumentRef] | None = None,
    raw_images: list[ImageRef] | None = None,
) -> ClaimState:
    """Initial state for `graph.invoke`. Every key is present so reducers can merge."""

    return {
        "claim_id": claim_id,
        "raw_documents": list(raw_documents or []),
        "raw_images": list(raw_images or []),
        "intake": None,
        "damage_assessment": None,
        "fraud_signal": None,
        "policy_determination": None,
        "verdict": None,
        "trace": [],
        "requires_human_review": False,
        "error": None,
    }
