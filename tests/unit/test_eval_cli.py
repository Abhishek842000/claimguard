from pathlib import Path

from claimguard.eval.run_eval import main, run_eval


def test_eval_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    assert main(["--dataset", "does-not-exist", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "does-not-exist.md").is_file()


def test_run_eval_empty_dataset_is_zero() -> None:
    report = run_eval(dataset_version="does-not-exist")
    assert report["n_cases"] == 0
    assert report["after"]["n_cases"] == 0
