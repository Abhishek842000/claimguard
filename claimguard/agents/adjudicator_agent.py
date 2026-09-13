"""Adjudicator — synthesize sub-agent outputs into a `TriageVerdict` and route."""

from __future__ import annotations

from claimguard.schemas.graph import GraphState


def run_adjudicator_agent(state: GraphState) -> GraphState:
    raise NotImplementedError("adjudicator_agent is implemented in Phase 3")
