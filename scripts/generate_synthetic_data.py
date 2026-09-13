#!/usr/bin/env python3
"""Generate synthetic FNOL PDFs, damage photos, notes, and the eval holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from claimguard.data_gen.constants import DEFAULT_EVAL_N, DEFAULT_N_CLAIMS, DEFAULT_SEED
from claimguard.data_gen.generate import generate_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=DEFAULT_N_CLAIMS)
    parser.add_argument("--eval-n", type=int, default=DEFAULT_EVAL_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--claims-dir", type=Path, default=None)
    parser.add_argument("--eval-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    summary = generate_dataset(
        n_claims=args.n,
        eval_n=args.eval_n,
        seed=args.seed,
        claims_dir=args.claims_dir,
        eval_dir=args.eval_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
