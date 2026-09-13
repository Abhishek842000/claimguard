"""Judge rubric. Default path is deterministic so eval does not need an API key.

`judge_v1` is the versioned prompt for an optional LLM swap-in.
"""

from __future__ import annotations

from claimguard.llm.prompts import load_prompt
from claimguard.schemas.common import ClaimGuardModel, UnitInterval
from pydantic import Field


class JudgeScores(ClaimGuardModel):
    grounding: UnitInterval = Field(description="Are citations actually in the retrieved set?")
    coherence: UnitInterval = Field(description="Is the memo internally consistent?")
    completeness: UnitInterval = Field(description="Did the verdict address coverage, fraud, and docs?")
    rationale: str = Field(description="Short judge explanation, no PII.")
    prompt_version: str = Field(default="judge_v1:1.0.0")


def judge_verdict(payload: dict[str, object]) -> JudgeScores:
    """Programmatic judge: citation ⊆ retrieved, verdict present, routing coherent."""
    prompt = load_prompt("judge_v1")
    retrieved = {str(item) for item in (payload.get("retrieved_ids") or [])}
    cited = {str(item) for item in (payload.get("cited_ids") or [])}
    if not cited:
        grounding = 1.0
    else:
        grounding = len(cited & retrieved) / len(cited)
    has_verdict = bool(payload.get("has_verdict"))
    routing_ok = bool(payload.get("routing_matches_gates"))
    completeness = 1.0 if has_verdict else 0.0
    coherence = 1.0 if (has_verdict and routing_ok) else 0.4 if has_verdict else 0.0
    return JudgeScores(
        grounding=round(grounding, 4),
        coherence=coherence,
        completeness=completeness,
        rationale=(
            f"Cited {len(cited)} clause(s); {len(cited & retrieved)} were retrieved. "
            f"Verdict present={has_verdict}; routing gates match={routing_ok}."
        ),
        prompt_version=f"{prompt.name}:{prompt.version}",
    )
