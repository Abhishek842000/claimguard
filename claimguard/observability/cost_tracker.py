"""Token and USD accounting per claim / agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class TokenUsage:
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


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
            TokenUsage(agent, model, input_tokens, output_tokens, cost_usd)
        )

    @property
    def total_cost_usd(self) -> Decimal:
        return sum((u.cost_usd for u in self.usages), Decimal("0"))

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self.usages)
