"""Policy agent — hybrid RAG over policy documents with cited clauses."""

from __future__ import annotations

from claimguard.schemas.graph import ClaimState, ClaimStateUpdate


def run_policy_agent(state: ClaimState) -> ClaimStateUpdate:
    raise NotImplementedError("policy_agent is implemented in a later phase")
