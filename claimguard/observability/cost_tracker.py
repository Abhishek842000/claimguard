"""Token and USD accounting per claim / agent.

In-memory `CostTracker` is the unit of a single pipeline run (tests + worker).
Process-wide interview numbers (`total`, `avg per claim`, `by agent`) come
from `summarize` over persisted `agent_traces` rows — the API and worker are
separate processes, so Postgres is the source of truth, not a module global.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class TokenUsage:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    claim_id: str | None = None


@dataclass(frozen=True)
class AgentCostBreakdown:
    agent: str
    cost_usd: Decimal
    tokens: int
    steps: int


@dataclass(frozen=True)
class CostSummary:
    total_cost_usd: Decimal
    claim_count: int
    average_cost_per_claim: Decimal
    by_agent: list[AgentCostBreakdown]


@dataclass
class CostTracker:
    """In-memory accumulator flushed to agent_traces at the end of a run."""

    claim_id: str
    usages: list[TokenUsage] = field(default_factory=list)

    def record(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
    ) -> None:
        self.usages.append(
            TokenUsage(
                agent=agent,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                claim_id=self.claim_id,
            )
        )

    @property
    def total_cost_usd(self) -> Decimal:
        return sum((u.cost_usd for u in self.usages), Decimal("0"))

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self.usages)

    def summary(self) -> CostSummary:
        return summarize(self.usages)


def summarize(usages: list[TokenUsage]) -> CostSummary:
    """Aggregate running totals for `/v1/metrics` and the dashboard panel."""
    claims = {u.claim_id for u in usages if u.claim_id}
    claim_count = len(claims)
    total = sum((u.cost_usd for u in usages), Decimal("0"))
    average = (total / claim_count) if claim_count else Decimal("0")
    buckets: dict[str, list[TokenUsage]] = defaultdict(list)
    for usage in usages:
        buckets[usage.agent].append(usage)
    by_agent = [
        AgentCostBreakdown(
            agent=agent,
            cost_usd=sum((u.cost_usd for u in rows), Decimal("0")),
            tokens=sum(u.input_tokens + u.output_tokens for u in rows),
            steps=len(rows),
        )
        for agent, rows in sorted(buckets.items())
    ]
    return CostSummary(
        total_cost_usd=total,
        claim_count=claim_count,
        average_cost_per_claim=average,
        by_agent=by_agent,
    )
