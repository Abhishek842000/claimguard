"""CLI: run the eval suite and persist a versioned results artifact.

Usage (Phase 4):
    uv run claimguard-eval --dataset v0 --out eval_runs/
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ClaimGuard evaluation harness.")
    parser.add_argument("--dataset", default="v0", help="Eval set version under data/eval_set/")
    parser.add_argument("--out", default="eval_runs", help="Directory for JSON/markdown results")
    parser.parse_args(argv)
    print(
        "Eval runner is stubbed in Phase 0. "
        "Phase 4 will score fraud P/R, groundedness, hallucination, latency, and cost.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
