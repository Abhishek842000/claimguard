"""Claim processing StateGraph.

Intended topology (Phase 1+):

    intake
      ├─(has images)─> vision ─┐
      ├─(no images)────────────┤
      ├────────────────> fraud ┼─> adjudicator ─> auto_resolve | human_review
      └────────────────> policy┘

Conditional edges:
- skip vision when `state.skip_vision` or `intake.images` is empty
- force human_review when fraud_risk or 1 - confidence exceeds thresholds
- mark failed when a non-recoverable GraphError is present
"""

from __future__ import annotations

from typing import Any


def build_claim_pipeline() -> Any:
    """Compile the LangGraph StateGraph. Wired in Phase 1."""
    raise NotImplementedError("LangGraph pipeline is implemented in Phase 1")
