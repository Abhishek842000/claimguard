"""Intake agent — parse PDFs, notes, and metadata into `ClaimIntake`.

Phase 1: OCR / PDF extract, NER, schema validation, missing-field list.
"""

from __future__ import annotations

from claimguard.schemas.graph import GraphState


def run_intake_agent(state: GraphState) -> GraphState:
    raise NotImplementedError("intake_agent is implemented in Phase 1")
