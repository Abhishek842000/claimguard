"""Celery tasks. The pipeline itself is wired in Phase 1."""

from uuid import UUID

from apps.worker.celery_app import celery_app


@celery_app.task(name="claimguard.process_claim", bind=True)
def process_claim(self, claim_id: str) -> dict[str, str]:
    """Run the LangGraph pipeline for one claim.

    Phase 0: acknowledge the enqueue so the worker process is exercisable.
    Next: load artifacts, invoke `build_claim_pipeline()`, persist verdict + trace.
    """
    UUID(claim_id)  # validate early; fail the task on garbage ids
    return {"claim_id": claim_id, "status": "not_implemented"}
