from claimguard.eval.run_eval import main


def test_eval_cli_exits_cleanly_in_phase_0() -> None:
    assert main(["--dataset", "v0"]) == 0
