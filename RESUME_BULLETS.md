# Resume bullets (from the v0 eval harness)

Numbers are from `uv run claimguard-eval --dataset v0 --out eval_runs` on the
18-case holdout (4 fraud / 14 legit). Source artifact: [`eval_runs/v0.json`](eval_runs/v0.json).
Do not round these into marketing copy that the JSON does not support.

- Built a LangGraph claims-triage pipeline (intake → parallel vision / fraud / policy → adjudicator) with hard routing gates (`confidence < 0.65` or `fraud_risk_score > 0.45` → human review), served asynchronously on FastAPI + Celery rather than a synchronous HTTP handler.
- Hybrid RAG (BM25 + pgvector + RRF) plus programmatic citation filters: on the 18-case v0 holdout, retrieval groundedness went from **0.0 → 1.0** and hallucination from **1.0 → 0.0** versus an unfiltered invented-clause baseline.
- Deterministic fraud rules (NOAA weather mismatch, EXIF offset, shared phone/VIN) plus RAG raised fraud **precision from 0.3333 → 1.0** (2 TP / **0 FP** / 2 FN / 14 TN) while holding **recall at 0.5**, versus a claimed-amount > $7500 baseline (2 TP / 4 FP) on the same 18 cases.
- Offline eval path (heuristic completers, no API key): **p50 13.7 ms / p95 17.0 ms**, **$0.001347 per claim**. Reproducible with `uv run claimguard-eval --dataset v0`.
- Production-shaped edges: PII redaction before logs and Langfuse, shared-secret API keys + sliding-window rate limits, 80 unit tests with mocked LLM calls, and versioned prompts only under `llm/prompts/`.
