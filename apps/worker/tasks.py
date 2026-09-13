"""Celery tasks. The worker loads artifacts, runs the graph, and persists state."""

from __future__ import annotations

from uuid import UUID

from claimguard.db.repository import load_claim_state, mark_processing, persist_pipeline_result
from claimguard.db.session import session_scope
from claimguard.graph.runtime import invoke_claim_pipeline
from claimguard.observability.pii_redaction import redact_pii

from apps.worker.celery_app import celery_app


@celery_app.task(name="claimguard.process_claim", bind=True)
def process_claim(self, claim_id: str) -> dict[str, str]:
    """Run the LangGraph pipeline for one claim and write verdict + trace."""

    parsed = UUID(claim_id)
    with session_scope() as session:
        mark_processing(session, parsed)
        state = load_claim_state(session, parsed)
    try:
        result = invoke_claim_pipeline(state)
    except Exception as exc:
        with session_scope() as session:
            claim_state = load_claim_state(session, parsed)
            claim_state["error"] = redact_pii(f"pipeline crashed: {type(exc).__name__}")
            claim_state["requires_human_review"] = True
            persist_pipeline_result(session, parsed, claim_state)
        raise
    with session_scope() as session:
        claim = persist_pipeline_result(session, parsed, result)
        status = claim.status
    return {"claim_id": claim_id, "status": status}
