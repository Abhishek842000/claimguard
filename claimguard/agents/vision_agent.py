"""Vision agent — damage classification / severity from claim photos."""

from __future__ import annotations

from claimguard.schemas.graph import ClaimState, ClaimStateUpdate


def run_vision_agent(state: ClaimState) -> ClaimStateUpdate:
    raise NotImplementedError("vision_agent is implemented in a later phase")
