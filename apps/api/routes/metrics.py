"""Cost dashboard payload. Aggregated from persisted agent_traces."""

from __future__ import annotations

from claimguard.db.repository import fetch_cost_metrics
from claimguard.db.session import session_scope
from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["metrics"])


@router.get("/metrics")
def get_metrics() -> dict[str, object]:
    with session_scope() as session:
        summary = fetch_cost_metrics(session)
    return {
        "total_cost_usd": str(summary.total_cost_usd),
        "claim_count": summary.claim_count,
        "average_cost_per_claim": str(summary.average_cost_per_claim),
        "by_agent": [
            {
                "agent": row.agent,
                "cost_usd": str(row.cost_usd),
                "tokens": row.tokens,
                "steps": row.steps,
            }
            for row in summary.by_agent
        ],
    }
