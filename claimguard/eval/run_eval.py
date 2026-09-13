"""CLI: run the eval suite and persist a versioned results artifact.

Usage:
    uv run claimguard-eval --dataset v0 --out eval_runs/
"""

from __future__ import annotations

import argparse
import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from claimguard.agents.adjudicator_agent import run_adjudicator_agent
from claimguard.agents.fraud_agent import run_fraud_agent
from claimguard.agents.intake_agent import intake_input_from_claim_dir, run_intake_agent
from claimguard.agents.policy_agent import run_policy_agent
from claimguard.agents.vision_agent import run_vision_agent
from claimguard.eval.dataset import EVAL_SET_DIR, load_eval_set
from claimguard.eval.llm_judge import judge_verdict
from claimguard.eval.metrics import EvalMetrics, compute_metrics
from claimguard.graph.claim_pipeline import PipelineAgents
from claimguard.graph.runtime import invoke_claim_pipeline
from claimguard.graph.routing import RoutingThresholds, decide_route
from claimguard.observability.langfuse import NullSink
from claimguard.observability.pii_redaction import redact_mapping
from claimguard.policy.grounding import filter_grounded_clauses
from claimguard.retrieval.hybrid_retriever import InMemoryRetriever, RetrievedChunk
from claimguard.schemas.common import RetrievalSource
from claimguard.schemas.graph import ClaimState, ClaimStateUpdate, empty_claim_state
from claimguard.schemas.intake import ClaimIntake
from claimguard.schemas.policy import CitedClause, PolicyDetermination

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAUD_THRESHOLD = 0.45
BASELINE_AMOUNT = Decimal("7500.00")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ClaimGuard evaluation harness.")
    parser.add_argument("--dataset", default="v0", help="Eval set version under data/eval_set/")
    parser.add_argument("--out", default="eval_runs", help="Directory for JSON/markdown results")
    args = parser.parse_args(argv)
    report = run_eval(dataset_version=args.dataset)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.dataset}.json"
    md_path = out_dir / f"{args.dataset}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(md_path.read_text(encoding="utf-8"))
    return 0


def run_eval(*, dataset_version: str = "v0") -> dict[str, Any]:
    cases = load_eval_set(dataset_version)
    policy_retriever = _markdown_retriever("policy")
    fraud_retriever = _markdown_retriever("fraud")
    after_rows: list[dict[str, object]] = []
    before_rows: list[dict[str, object]] = []
    case_rows: list[dict[str, object]] = []
    for case in cases:
        scored = _score_case(case, policy_retriever=policy_retriever, fraud_retriever=fraud_retriever)
        after_rows.append(scored["after"])
        before_rows.append(scored["before"])
        case_rows.append(scored["summary"])
    after = compute_metrics(after_rows)
    before = compute_metrics(before_rows)
    return {
        "dataset_version": dataset_version,
        "n_cases": len(cases),
        "before": before.as_dict(),
        "after": after.as_dict(),
        "cases": case_rows,
    }


def _score_case(
    case: dict[str, Any],
    *,
    policy_retriever: InMemoryRetriever,
    fraud_retriever: InMemoryRetriever,
) -> dict[str, Any]:
    claim_id = str(case["claim_id"])
    case_dir = EVAL_SET_DIR / "cases" / claim_id
    raw_path = case_dir / "claim.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.is_file() else {}
    payload = intake_input_from_claim_dir(case_dir)
    state = empty_claim_state(
        claim_id,
        raw_documents=payload.raw_documents,
        raw_images=payload.raw_images,
    )
    agents = PipelineAgents(
        intake_agent=_intake_with_overlay(raw),
        vision_agent=run_vision_agent,
        fraud_agent=lambda s: run_fraud_agent(s, retriever=fraud_retriever),
        policy_agent=lambda s: run_policy_agent(s, retriever=policy_retriever),
        adjudicator_agent=run_adjudicator_agent,
    )
    started = time.perf_counter()
    result = invoke_claim_pipeline(state, agents=agents, sink=NullSink())
    latency_ms = (time.perf_counter() - started) * 1000
    cost = sum((step.cost_usd for step in result.get("trace") or []), Decimal("0"))
    truth = case.get("ground_truth_fraud_label") == "fraud"
    fraud = result.get("fraud_signal")
    policy = result.get("policy_determination")
    verdict = result.get("verdict")
    pred = bool(fraud and fraud.fraud_risk_score > FRAUD_THRESHOLD)
    claimed = Decimal("0")
    intake = result.get("intake")
    if intake is not None:
        claimed = intake.claimed_amount.amount
    baseline_pred = claimed > BASELINE_AMOUNT
    retrieved_ids = list(policy.retrieved_chunk_ids) if policy else []
    cited_ids = [clause.clause_id for clause in (policy.supporting_clauses if policy else [])]
    cited_ids.extend(clause.clause_id for clause in (policy.exclusions_applied if policy else []))
    planted = filter_grounded_clauses(
        _with_planted_hallucination(policy, retrieved_ids),
        set(retrieved_ids),
    )
    judge = judge_verdict(
        {
            "retrieved_ids": retrieved_ids,
            "cited_ids": cited_ids,
            "has_verdict": verdict is not None,
            "routing_matches_gates": _routing_matches(result),
        }
    )
    after = {
        "y_true_fraud": truth,
        "y_pred_fraud": pred,
        "grounded": bool(policy.grounded) if policy else False,
        "latency_ms": latency_ms,
        "cost_usd": cost,
    }
    before = {
        "y_true_fraud": truth,
        "y_pred_fraud": baseline_pred,
        "grounded": False,
        "latency_ms": latency_ms,
        "cost_usd": cost,
    }
    summary = redact_mapping(
        {
            "claim_id": claim_id,
            "y_true_fraud": truth,
            "y_pred_fraud": pred,
            "baseline_pred_fraud": baseline_pred,
            "fraud_risk_score": float(fraud.fraud_risk_score) if fraud else None,
            "rule_hits": [hit.rule_id for hit in (fraud.rule_hits if fraud else [])],
            "grounded": after["grounded"],
            "planted_hallucination_caught": planted.grounded is False,
            "judge": judge.model_dump(mode="json"),
            "latency_ms": round(latency_ms, 1),
            "cost_usd": str(cost),
        }
    )
    return {"after": after, "before": before, "summary": summary}


def _intake_with_overlay(raw: dict[str, Any]):
    def node(state: ClaimState) -> ClaimStateUpdate:
        update = run_intake_agent(state)
        intake = update.get("intake")
        if isinstance(intake, ClaimIntake):
            update["intake"] = _overlay_fnol(intake, raw)
        return update

    return node


def _overlay_fnol(intake: ClaimIntake, raw: dict[str, Any]) -> ClaimIntake:
    """Fill phone/email/VIN from the case sidecar when the PDF parse left them blank."""
    from datetime import date as date_cls

    claimant = raw.get("claimant") or {}
    incident_raw = raw.get("incident") or {}
    vehicle_raw = incident_raw.get("vehicle") or {}
    claimant_update: dict[str, object] = {}
    if not intake.claimant.phone and claimant.get("phone"):
        claimant_update["phone"] = claimant["phone"]
    if not intake.claimant.email and claimant.get("email"):
        claimant_update["email"] = claimant["email"]
    next_claimant = intake.claimant.model_copy(update=claimant_update) if claimant_update else intake.claimant
    incident_update: dict[str, object] = {}
    vehicle = intake.incident.vehicle
    if vehicle is not None and not vehicle.vin and vehicle_raw.get("vin"):
        vehicle = vehicle.model_copy(update={"vin": vehicle_raw["vin"]})
        incident_update["vehicle"] = vehicle
    raw_date = incident_raw.get("incident_date")
    if intake.incident.incident_date.year < 2000 and isinstance(raw_date, str):
        incident_update["incident_date"] = date_cls.fromisoformat(raw_date[:10])
    incident = intake.incident.model_copy(update=incident_update) if incident_update else intake.incident
    return intake.model_copy(update={"claimant": next_claimant, "incident": incident})


def _with_planted_hallucination(
    policy: PolicyDetermination | None,
    retrieved_ids: list[str],
) -> PolicyDetermination:
    fake = CitedClause(
        document_id="pap-invented",
        document_title="Invented",
        clause_id="pap-invented-99",
        section="Hallucinated",
        quote="This clause was never retrieved.",
        relevance=0.9,
        source=RetrievalSource.DENSE,
    )
    if policy is None:
        from claimguard.schemas.common import CoverageStatus

        return PolicyDetermination(
            claim_id="00000000-0000-4000-8000-000000000000",
            coverage_status=CoverageStatus.INSUFFICIENT_INFORMATION,
            supporting_clauses=[fake],
            retrieved_chunk_ids=retrieved_ids,
            grounded=True,
            rationale="baseline",
            confidence=0.1,
        )
    return policy.model_copy(update={"supporting_clauses": [*policy.supporting_clauses, fake]})


def _routing_matches(state: ClaimState) -> bool:
    verdict = state.get("verdict")
    if verdict is None:
        return False
    expected = decide_route(state, RoutingThresholds())
    return verdict.human_review_required is (expected == "route_to_human")


def _markdown_retriever(corpus: str) -> InMemoryRetriever:
    folder = REPO_ROOT / "data" / ("policy_docs" if corpus == "policy" else "fraud_corpus")
    chunks: list[RetrievedChunk] = []
    for path in sorted(folder.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        chunks.append(
            RetrievedChunk(
                chunk_id=path.stem,
                title=path.stem,
                text=text[:900],
                score=0.2,
                source=RetrievalSource.BM25,
            )
        )
    return InMemoryRetriever(chunks)


def _markdown(report: dict[str, Any]) -> str:
    before = report["before"]
    after = report["after"]
    lines = [
        f"# Eval {report['dataset_version']} ({report['n_cases']} holdout cases)",
        "",
        "| Metric | Baseline | ClaimGuard |",
        "|--------|----------|------------|",
        f"| Fraud precision | {_fmt(before['fraud_precision'])} | {_fmt(after['fraud_precision'])} |",
        f"| Fraud recall | {_fmt(before['fraud_recall'])} | {_fmt(after['fraud_recall'])} |",
        f"| Retrieval groundedness | {_fmt(before['groundedness'])} | {_fmt(after['groundedness'])} |",
        f"| Hallucination rate | {_fmt(before['hallucination_rate'])} | {_fmt(after['hallucination_rate'])} |",
        f"| Latency p50 / p95 (ms) | {_fmt(before['latency_p50_ms'])} / {_fmt(before['latency_p95_ms'])} | {_fmt(after['latency_p50_ms'])} / {_fmt(after['latency_p95_ms'])} |",
        f"| Cost per claim (USD) | {_fmt(before['cost_per_claim_usd'])} | {_fmt(after['cost_per_claim_usd'])} |",
        "",
        "Baseline fraud = claimed amount > $7500. Baseline groundedness = unfiltered invented clause IDs.",
        "ClaimGuard fraud = `fraud_risk_score > 0.45` after rules + RAG. Groundedness = citation ⊆ retrieved.",
        "",
    ]
    return "\n".join(lines)


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
