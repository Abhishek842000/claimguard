"""The eval package must stay importable even before Phase 4 lands."""

from claimguard.eval.dataset import EVAL_SET_DIR, load_eval_set
from claimguard.eval.llm_judge import JudgeScores


def test_eval_set_dir_exists() -> None:
    assert EVAL_SET_DIR.name == "eval_set"


def test_empty_eval_set_returns_empty_list() -> None:
    assert load_eval_set("does-not-exist") == []


def test_judge_schema_example() -> None:
    scores = JudgeScores(
        grounding=0.9,
        coherence=0.8,
        completeness=0.7,
        rationale="Cited clauses were present in the retrieved set.",
    )
    assert scores.grounding == 0.9
