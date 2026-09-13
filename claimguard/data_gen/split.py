"""Stratified holdout. Eval ids must never appear under synthetic_claims/."""

from __future__ import annotations

from collections import defaultdict
from random import Random
from typing import Any


def hold_out_eval(
    claims: list[dict[str, Any]],
    rng: Random,
    eval_n: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (dev, eval) with fraud rate and LOB roughly preserved."""
    if eval_n <= 0 or eval_n >= len(claims):
        raise ValueError("eval_n must be between 1 and n_claims - 1")

    buckets: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        key = (claim["line_of_business"], bool(claim["ground_truth"]["is_fraud"]))
        buckets[key].append(claim)

    eval_claims: list[dict[str, Any]] = []
    # Guarantee ~20% fraud in the holdout so precision/recall is measurable.
    fraud = [c for c in claims if c["ground_truth"]["is_fraud"]]
    rng.shuffle(fraud)
    n_fraud = min(len(fraud), max(1, round(eval_n * 0.20)))
    eval_claims.extend(fraud[:n_fraud])

    remaining = eval_n - len(eval_claims)
    bucket_items = list(buckets.items())
    rng.shuffle(bucket_items)
    taken_ids = {c["claim_id"] for c in eval_claims}
    for _key, group in bucket_items:
        if remaining <= 0:
            break
        if _key[1]:
            # Fraud already reserved above; do not overweight the holdout.
            continue
        unused = [c for c in group if c["claim_id"] not in taken_ids]
        share = max(1, round(eval_n * len(group) / len(claims)))
        take = min(len(unused), share, remaining)
        rng.shuffle(unused)
        chosen = unused[:take]
        eval_claims.extend(chosen)
        taken_ids.update(c["claim_id"] for c in chosen)
        remaining -= take

    eval_ids = {c["claim_id"] for c in eval_claims}
    unused = [c for c in claims if c["claim_id"] not in eval_ids]
    legit = [c for c in unused if not c["ground_truth"]["is_fraud"]]
    extra_fraud = [c for c in unused if c["ground_truth"]["is_fraud"]]
    rng.shuffle(legit)
    leftovers = legit + extra_fraud
    while remaining > 0 and leftovers:
        extra = leftovers.pop()
        eval_claims.append(extra)
        eval_ids.add(extra["claim_id"])
        remaining -= 1

    for claim in eval_claims:
        claim["split"] = "eval"
    dev = [c for c in claims if c["claim_id"] not in eval_ids]
    for claim in dev:
        claim["split"] = "dev"
    return dev, eval_claims


def assert_no_leak(dev_ids: set[str], eval_ids: set[str]) -> None:
    overlap = dev_ids & eval_ids
    if overlap:
        raise RuntimeError(f"Eval ids leaked into the dev pool: {sorted(overlap)[:5]}")
