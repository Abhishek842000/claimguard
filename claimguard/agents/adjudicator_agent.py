"""Adjudicator — synthesize sub-agent outputs into a `TriageVerdict`."""

from __future__ import annotations

from claimguard.schemas.graph import ClaimState, ClaimStateUpdate


def run_adjudicator_agent(state: ClaimState) -> ClaimStateUpdate:
    raise NotImplementedError("adjudicator_agent is implemented in a later phase")
