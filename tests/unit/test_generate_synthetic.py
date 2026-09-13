import json
from pathlib import Path

from claimguard.data_gen.constants import TARGET_FRAUD_RATE
from claimguard.data_gen.generate import generate_dataset


def test_generate_writes_dev_and_held_out_eval(tmp_path: Path) -> None:
    claims_dir = tmp_path / "synthetic_claims"
    eval_dir = tmp_path / "eval_set"
    summary = generate_dataset(
        n_claims=20,
        eval_n=6,
        seed=7,
        claims_dir=claims_dir,
        eval_dir=eval_dir,
    )
    assert summary["n_dev"] == 14
    assert summary["n_eval"] == 6
    dev_ids = {p.name for p in claims_dir.iterdir() if p.is_dir()}
    eval_ids = {p.name for p in (eval_dir / "cases").iterdir() if p.is_dir()}
    assert dev_ids.isdisjoint(eval_ids)
    assert summary["n_fraud_dev"] + summary["n_fraud_eval"] == round(20 * TARGET_FRAUD_RATE)

    sample_dev = next(claims_dir.glob("*/claim.json"))
    dev_payload = json.loads(sample_dev.read_text())
    assert "ground_truth" not in dev_payload
    assert (sample_dev.parent / "documents" / "fnol-claim-form.pdf").is_file()
    assert (sample_dev.parent / "notes.txt").is_file()
    assert list((sample_dev.parent / "images").glob("*.jpg"))

    eval_row = json.loads((eval_dir / "v0.jsonl").read_text().splitlines()[0])
    assert "ground_truth_fraud_label" in eval_row
    assert eval_row["ground_truth_verdict"]["coverage_status"]
    eval_claim = json.loads((eval_dir / "cases" / eval_row["claim_id"] / "claim.json").read_text())
    assert "ground_truth" in eval_claim


def test_generate_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    first = generate_dataset(n_claims=8, eval_n=3, seed=1, claims_dir=a / "c", eval_dir=a / "e")
    second = generate_dataset(n_claims=8, eval_n=3, seed=1, claims_dir=b / "c", eval_dir=b / "e")
    assert json.loads((a / "c" / "SPLIT.json").read_text()) == json.loads(
        (b / "c" / "SPLIT.json").read_text()
    )
    assert first["n_eval"] == second["n_eval"]
