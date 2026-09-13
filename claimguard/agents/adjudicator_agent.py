"""Adjudicator — synthesize specialist outputs. Routing gates stay in the graph."""

from __future__ import annotations

import json
from decimal import Decimal

from claimguard.graph.routing import RoutingThresholds
from claimguard.llm.prompts import load_prompt
from claimguard.llm.structured_output import Completer, generate_structured
from claimguard.observability.pii_redaction import redact_mapping
from claimguard.schemas.common import CoverageStatus, DocumentType, Money, RoutingDecision
from claimguard.schemas.graph import AgentStep, ClaimState, ClaimStateUpdate
from claimguard.schemas.policy import PolicyDetermination
from claimguard.schemas.verdict import MissingDocument, SettlementMemo, TriageVerdict


def run_adjudicator_agent(
    state: ClaimState,
    *,
    completer: Completer | None = None,
    thresholds: RoutingThresholds | None = None,
) -> ClaimStateUpdate:
    gates = thresholds or RoutingThresholds.from_settings()
    prompt = load_prompt("adjudicator_v1")
    used = completer or _HeuristicMemoCompleter(state)
    result = generate_structured(
        prompt.render_user(
            intake_json=_dump(state.get("intake")),
            damage_json=_dump(state.get("damage_assessment")),
            fraud_json=_dump(state.get("fraud_signal")),
            policy_json=_dump(state.get("policy_determination")),
        ),
        SettlementMemo,
        completer=used,
        system=prompt.system,
    )
    if not result.ok or result.value is None:
        memo = SettlementMemo(
            summary="Adjudicator could not draft a memo; route to a human.",
            caveats=["structured output exhausted"],
        )
        attempts = result.attempts
    else:
        memo = result.value
        attempts = result.attempts

    verdict = _build_verdict(state, memo, gates)
    return {
        "verdict": verdict,
        "trace": [
            AgentStep.completed(
                "adjudicator_agent",
                output_schema="TriageVerdict",
                prompt_version=f"{prompt.name}:{prompt.version}",
                model="heuristic-offline" if completer is None else "injected",
                output_snapshot=verdict.model_dump(mode="json"),
                metadata={"attempts": attempts},
            )
        ],
    }


def _build_verdict(
    state: ClaimState,
    memo: SettlementMemo,
    gates: RoutingThresholds,
) -> TriageVerdict:
    intake = state.get("intake")
    damage = state.get("damage_assessment")
    fraud = state.get("fraud_signal")
    policy = state.get("policy_determination")
    claim_id = intake.claim_id if intake is not None else _uuid(state["claim_id"])

    severity = damage.severity_score if damage is not None else 0.3
    fraud_score = fraud.fraud_risk_score if fraud is not None else 0.5
    coverage = policy or PolicyDetermination(
        claim_id=claim_id,
        coverage_status=CoverageStatus.INSUFFICIENT_INFORMATION,
        rationale="Policy agent did not produce a determination.",
        confidence=0.2,
        grounded=False,
    )
    confidences = [
        value
        for value in (
            intake.intake_confidence if intake is not None else None,
            damage.confidence if damage is not None else None,
            fraud.confidence if fraud is not None else None,
            coverage.confidence,
        )
        if value is not None
    ]
    overall = min(confidences) if confidences else 0.3
    reasons: list[str] = []
    if state.get("error"):
        reasons.append(f"upstream error: {state['error']}")
    if overall < gates.confidence:
        reasons.append(f"confidence {overall:.2f} < {gates.confidence:.2f}")
    if fraud_score > gates.fraud_score:
        reasons.append(f"fraud_score {fraud_score:.2f} > {gates.fraud_score:.2f}")
    if str(coverage.coverage_status) == CoverageStatus.INSUFFICIENT_INFORMATION:
        reasons.append("coverage_status is insufficient_information")
    missing: list[MissingDocument] = []
    if intake is not None and intake.incident.third_party_involved and not intake.incident.police_report_number:
        missing.append(
            MissingDocument(
                document_type=DocumentType.POLICE_REPORT,
                reason="Third-party incident with no police report number.",
                required_for="compliance",
                blocking=True,
            )
        )
    if any(doc.blocking for doc in missing):
        reasons.append("blocking missing document")
    human = bool(reasons) or bool(state.get("error"))
    return TriageVerdict(
        claim_id=claim_id,
        severity_score=severity,
        fraud_risk_score=fraud_score,
        coverage=coverage,
        missing_documents=missing,
        settlement_memo=memo,
        routing=RoutingDecision.HUMAN_REVIEW if human else RoutingDecision.AUTO_RESOLVE,
        routing_reasons=reasons or ["thresholds cleared"],
        overall_confidence=overall,
        human_review_required=human,
        prompt_versions={"adjudicator": "adjudicator_v1"},
    )


def _dump(model: object) -> str:
    if model is None:
        return "null"
    payload = model.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.dumps(redact_mapping(payload), indent=2)


def _uuid(value: str):
    from uuid import UUID

    return UUID(value)


class _HeuristicMemoCompleter:
    def __init__(self, state: ClaimState) -> None:
        self.state = state

    def complete(self, messages: list[dict[str, str]], *, schema_name: str) -> str:
        intake = self.state.get("intake")
        fraud = self.state.get("fraud_signal")
        policy = self.state.get("policy_determination")
        summary = (
            f"Incident {intake.incident.incident_type if intake else 'unknown'}. "
            f"Fraud score {fraud.fraud_risk_score if fraud else 'n/a'}. "
            f"Coverage {policy.coverage_status if policy else 'unknown'}."
        )
        payout = None
        if policy is not None and policy.estimated_payable is not None:
            payout = policy.estimated_payable
        elif intake is not None:
            payout = Money(amount=Decimal(intake.claimed_amount.amount))
        memo = SettlementMemo(
            summary=summary,
            recommended_payout=payout,
            conditions=["Human review if any fraud or coverage gate fired."],
            caveats=["Memo drafted offline without a live LLM."],
        )
        return memo.model_dump_json()
