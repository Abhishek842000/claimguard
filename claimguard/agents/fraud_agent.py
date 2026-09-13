"""Fraud agent — hybrid RAG over the fraud corpus plus deterministic rule hits."""

from __future__ import annotations

from claimguard.schemas.graph import ClaimState, ClaimStateUpdate


def run_fraud_agent(state: ClaimState) -> ClaimStateUpdate:
    raise NotImplementedError("fraud_agent is implemented in a later phase")
