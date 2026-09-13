# Labeled eval set (held out)

`v0.jsonl` is the only labeled set that may be used for **scoring**.

Rules:

- Eval claim ids live under `cases/` and in `holdout_ids.json`.
- They are **not** copied into `data/synthetic_claims/`.
- Do not use these files for prompt iteration, few-shot examples, or
  retrieval-index construction. The corpora (`policy_docs/`, `fraud_corpus/`)
  are independently written specimen text — they do not contain eval claims.

Regenerate with `uv run python scripts/generate_synthetic_data.py`.

Each JSONL row:

- `claim_id`
- `inputs` (paths to PDF, notes, images)
- `ground_truth_fraud_label` (`fraud` | `legitimate`)
- `ground_truth_verdict` (coverage_status, severity_band, expected_routing)
- `injected_fraud_signals` (empty on legitimate claims)
