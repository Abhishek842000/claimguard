#!/usr/bin/env python3
"""Write the labeled holdout. Same entry point as generate_synthetic_data."""

from __future__ import annotations

import json
import sys

from claimguard.data_gen.generate import generate_dataset


def main(argv: list[str] | None = None) -> int:
    if argv:
        print(
            "seed_eval_set.py ignores extra flags; use scripts/generate_synthetic_data.py "
            "to change n / seed.",
            file=sys.stderr,
        )
    summary = generate_dataset()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
