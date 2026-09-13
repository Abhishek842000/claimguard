"""Intake agent — parse PDFs, notes, and metadata into `ClaimIntake`."""

from __future__ import annotations

from claimguard.schemas.graph import ClaimState, ClaimStateUpdate


def run_intake_agent(state: ClaimState) -> ClaimStateUpdate:
    raise NotImplementedError("intake_agent is implemented in a later phase")
