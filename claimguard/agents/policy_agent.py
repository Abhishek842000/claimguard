"""Policy agent — hybrid RAG over policy docs with programmatic citation checks."""

from __future__ import annotations

import json
from decimal import Decimal

from claimguard.llm.prompts import load_prompt
from claimguard.llm.structured_output import Completer, generate_structured
from claimguard.observability.pii_redaction import redact_mapping
from claimguard.policy.grounding import filter_grounded_clauses
from claimguard.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk, Retriever
from claimguard.schemas.common import CoverageStatus, Money, RetrievalSource
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate
from claimguard.schemas.intake import ClaimIntake
from claimguard.schemas.policy import CitedClause, PolicyDetermination


def run_policy_agent(
    state: ClaimState,
    *,
    completer: Completer | None = None,
    retriever: Retriever | None = None,
) -> ClaimStateUpdate:
    intake = state.get("intake")
    if intake is None:
        return {
            "error": "policy_agent: intake is missing",
            "requires_human_review": True,
            "trace": [
                AgentStep.completed(
                    "policy_agent",
                    status="error",
                    error="intake is missing",
                    output_schema="PolicyDetermination",
                )
            ],
        }

    searcher = retriever or HybridRetriever("policy")
    query = _query(intake)
    chunks = searcher.search(query, k=6)
    retrieved_ids = {chunk.chunk_id for chunk in chunks}
    prompt = load_prompt("policy_v1")
    used = completer or _HeuristicPolicyCompleter(intake, chunks)
    result = generate_structured(
        prompt.render_user(
            intake_json=json.dumps(redact_mapping(intake.model_dump(mode="json")), indent=2),
            retrieved_chunks=json.dumps(
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "title": chunk.title,
                        "text": chunk.text,
                    }
                    for chunk in chunks
                ],
                indent=2,
            ),
        ),
        PolicyDetermination,
        completer=used,
        system=prompt.system,
    )
    if not result.ok or result.value is None:
        return {
            "error": f"policy_agent structured output exhausted after {result.attempts} attempt(s)",
            "requires_human_review": True,
            "trace": [
                AgentStep.completed(
                    "policy_agent",
                    status="error",
                    error="structured output exhausted",
                    prompt_version=f"{prompt.name}:{prompt.version}",
                    metadata={"attempts": result.attempts},
                )
            ],
        }

    grounded = filter_grounded_clauses(result.value, retrieved_ids)
    grounded = grounded.model_copy(update={"claim_id": intake.claim_id})
    return {
        "policy_determination": grounded,
        "trace": [
            AgentStep.completed(
                "policy_agent",
                output_schema="PolicyDetermination",
                prompt_version=f"{prompt.name}:{prompt.version}",
                model="heuristic-offline" if completer is None else "injected",
                output_snapshot=grounded.model_dump(mode="json"),
                metadata={
                    "attempts": result.attempts,
                    "retrieved": sorted(retrieved_ids),
                    "grounded": grounded.grounded,
                },
            )
        ],
    }


def _query(intake: ClaimIntake) -> str:
    return (
        f"{intake.incident.incident_type} {intake.incident.description} "
        "coverage exclusion deductible other than collision"
    )


class _HeuristicPolicyCompleter:
    def __init__(self, intake: ClaimIntake, chunks: list[RetrievedChunk]) -> None:
        self.intake = intake
        self.chunks = chunks

    def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str:
        clauses = [
            CitedClause(
                document_id=chunk.chunk_id.split(":")[0],
                document_title=chunk.title,
                clause_id=chunk.chunk_id,
                section=chunk.title,
                quote=chunk.text[:400],
                relevance=min(1.0, chunk.score if chunk.score <= 1 else 0.6),
                source=RetrievalSource.RRF,
            )
            for chunk in self.chunks[:3]
        ]
        peril = str(self.intake.incident.incident_type)
        excluded = any("exclusion" in chunk.chunk_id or "flood" in chunk.text.lower() for chunk in self.chunks)
        if "theft" in peril and excluded:
            status = CoverageStatus.EXCLUDED
        elif clauses:
            status = CoverageStatus.COVERED
        else:
            status = CoverageStatus.INSUFFICIENT_INFORMATION
        deductible = Money(amount=Decimal("500.00"))
        claimed = self.intake.claimed_amount.amount
        payable = Money(amount=max(Decimal("0"), claimed - deductible.amount))
        determination = PolicyDetermination(
            claim_id=self.intake.claim_id,
            coverage_status=status,
            covered_perils=[peril] if status == CoverageStatus.COVERED else [],
            supporting_clauses=clauses if status != CoverageStatus.EXCLUDED else [],
            exclusions_applied=clauses if status == CoverageStatus.EXCLUDED else [],
            deductible=deductible,
            estimated_payable=payable if status == CoverageStatus.COVERED else None,
            rationale=(
                f"Coverage {status} using retrieved clause ids "
                + ", ".join(clause.clause_id for clause in clauses)
            ),
            retrieved_chunk_ids=[chunk.chunk_id for chunk in self.chunks],
            grounded=True,
            confidence=0.72 if clauses else 0.4,
        )
        return determination.model_dump_json()
