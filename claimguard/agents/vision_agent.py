"""Vision agent — damage classification / severity from claim photos."""

from __future__ import annotations

from claimguard.schemas.graph import GraphState


def run_vision_agent(state: GraphState) -> GraphState:
    raise NotImplementedError("vision_agent is implemented in Phase 2")
