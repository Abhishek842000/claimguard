"""Fraud agent — hybrid RAG over the fraud corpus plus deterministic rule hits."""

from __future__ import annotations

from claimguard.schemas.graph import GraphState


def run_fraud_agent(state: GraphState) -> GraphState:
    raise NotImplementedError("fraud_agent is implemented in Phase 3")
