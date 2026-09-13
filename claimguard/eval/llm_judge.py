"""LLM-as-judge rubric: grounding, coherence, completeness."""

from __future__ import annotations

from pydantic import Field

from claimguard.schemas.common import ClaimGuardModel, UnitInterval


class JudgeScores(ClaimGuardModel):
    grounding: UnitInterval = Field(description="Are citations actually in the retrieved set?")
    coherence: UnitInterval = Field(description="Is the memo internally consistent?")
    completeness: UnitInterval = Field(description="Did the verdict address coverage, fraud, and docs?")
    rationale: str = Field(description="Short judge explanation, no PII.")


def judge_verdict(_payload: dict[str, object]) -> JudgeScores:
    raise NotImplementedError("LLM judge is implemented in Phase 4")
