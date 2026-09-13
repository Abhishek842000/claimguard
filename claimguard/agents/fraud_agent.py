"""Fraud agent — hybrid RAG + deterministic rules + structured synthesis."""

from __future__ import annotations

import json

from claimguard.fraud.rules import evaluate_fraud_rules
from claimguard.llm.prompts import load_prompt
from claimguard.llm.structured_output import Completer, generate_structured
from claimguard.observability.pii_redaction import redact_mapping
from claimguard.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk, Retriever
from claimguard.schemas.common import RetrievalSource, RiskTier
from claimguard.schemas.fraud import FraudRuleHit, FraudSignal, SimilarFraudCase
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate
from claimguard.schemas.intake import ClaimIntake


def run_fraud_agent(
    state: ClaimState,
    *,
    completer: Completer | None = None,
    retriever: Retriever | None = None,
) -> ClaimStateUpdate:
    intake = state.get("intake")
    if intake is None:
        return {
            "error": "fraud_agent: intake is missing",
            "requires_human_review": True,
            "trace": [
                AgentStep.completed(
                    "fraud_agent",
                    status="error",
                    error="intake is missing",
                    output_schema="FraudSignal",
                )
            ],
        }

    searcher = retriever or HybridRetriever("fraud")
    query = _query(intake)
    chunks = searcher.search(query, k=5)
    rules = evaluate_fraud_rules(intake)
    prompt = load_prompt("fraud_v1")
    used = completer or _HeuristicFraudCompleter(intake, rules, chunks)
    result = generate_structured(
        prompt.render_user(
            intake_json=json.dumps(redact_mapping(intake.model_dump(mode="json")), indent=2),
            rule_hits=json.dumps([hit.model_dump(mode="json") for hit in rules], indent=2),
            retrieved_chunks=json.dumps(
                [chunk.__dict__ | {"source": str(chunk.source)} for chunk in chunks],
                indent=2,
                default=str,
            ),
        ),
        FraudSignal,
        completer=used,
        system=prompt.system,
    )
    if not result.ok or result.value is None:
        return {
            "error": f"fraud_agent structured output exhausted after {result.attempts} attempt(s)",
            "requires_human_review": True,
            "trace": [
                AgentStep.completed(
                    "fraud_agent",
                    status="error",
                    error="structured output exhausted",
                    prompt_version=f"{prompt.name}:{prompt.version}",
                    metadata={"attempts": result.attempts},
                )
            ],
        }
    signal = result.value.model_copy(
        update={
            "claim_id": intake.claim_id,
            "rule_hits": rules or result.value.rule_hits,
            "retrieved_chunk_ids": [chunk.chunk_id for chunk in chunks],
        }
    )
    return {
        "fraud_signal": signal,
        "trace": [
            AgentStep.completed(
                "fraud_agent",
                output_schema="FraudSignal",
                prompt_version=f"{prompt.name}:{prompt.version}",
                model="heuristic-offline" if completer is None else "injected",
                output_snapshot=signal.model_dump(mode="json"),
                metadata={"attempts": result.attempts, "retrieved": [c.chunk_id for c in chunks]},
            )
        ],
    }


def _query(intake: ClaimIntake) -> str:
    return (
        f"{intake.incident.incident_type} {intake.incident.description} "
        f"{' '.join(hit.rule_id for hit in evaluate_fraud_rules(intake))}"
    )


class _HeuristicFraudCompleter:
    def __init__(
        self,
        intake: ClaimIntake,
        rules: list[FraudRuleHit],
        chunks: list[RetrievedChunk],
    ) -> None:
        self.intake = intake
        self.rules = rules
        self.chunks = chunks

    def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str:
        high = any(rule.severity == "high" for rule in self.rules)
        score = min(0.95, 0.12 + 0.22 * len(self.rules) + (0.25 if high else 0.0))
        cases = [
            SimilarFraudCase(
                case_id=chunk.chunk_id,
                similarity=min(1.0, chunk.score if chunk.score <= 1 else chunk.score / (chunk.score + 1)),
                source=chunk.source if isinstance(chunk.source, RetrievalSource) else RetrievalSource.RRF,
                excerpt=chunk.text[:400],
                citation=chunk.title,
            )
            for chunk in self.chunks[:3]
        ]
        cited = ", ".join(rule.rule_id for rule in self.rules) or "no rules"
        cases_cited = ", ".join(case.case_id for case in cases) or "no cases"
        signal = FraudSignal(
            claim_id=self.intake.claim_id,
            fraud_risk_score=round(score, 2),
            risk_tier=RiskTier.HIGH if score >= 0.6 else RiskTier.MEDIUM if score >= 0.35 else RiskTier.LOW,
            rule_hits=self.rules,
            similar_cases=cases,
            justification=(
                f"Rules fired: {cited}. Retrieved patterns: {cases_cited}. "
                "Score is a deterministic function of rule severity, not an invented narrative."
            ),
            retrieved_chunk_ids=[chunk.chunk_id for chunk in self.chunks],
            grounded=True,
            confidence=0.78 if self.rules or self.chunks else 0.55,
        )
        return signal.model_dump_json()
