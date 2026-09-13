# Progress log

Running build diary. Newest phase at the bottom. Update this file at the end
of every phase, including what passed acceptance and what was deferred.

---

## Phase 0 — Scaffolding & infra (2026-09-12)

**Goal:** a monorepo a hiring manager can clone, with Compose, migrations,
Pydantic contracts, and a pytest harness — before any agent logic.

### Done

- uv package (`claimguard` + `apps`) on Python 3.12, Ruff + pytest configured
- FastAPI app factory with `GET /health` (Postgres + Redis readiness)
- Celery worker skeleton (`claimguard.process_claim`) and `claims` queue
- Docker Compose: `postgres` (pgvector/pg16), `redis`, `migrate`, `api`,
  `worker`, plus a namespaced Langfuse v3 stack (`langfuse-db`, ClickHouse,
  MinIO, `langfuse-web`, `langfuse-worker`) adapted from the official file
- Alembic `0001_initial`: `claims`, `claim_documents`, `claim_images`,
  `agent_traces`, `eval_runs`, `policy_chunks`, `fraud_case_chunks`
  (HNSW cosine indexes, 384-d embeddings)
- Full Pydantic schema set with field descriptions and `extra="forbid"`
- Working PII redactor + cost tracker (used from day one, not stubs)
- Versioned prompt YAML headers (`intake_v1`, `fraud_v1`, `policy_v1`,
  `adjudicator_v1`)
- pytest fixtures: `sample_claim`, `mocked_llm_responses`, `test_db`
- Next.js 15 frontend scaffold on port 3001
- Hiring-manager README + this log

### Acceptance

- [x] `uv run pytest` — 16 passed (no Docker required)
- [x] `docker compose up --build` brings every service up (api, worker, postgres,
      redis, migrate, langfuse-web/worker, langfuse-db, clickhouse, minio)
- [x] `GET /health` returns 200 with live Postgres + Redis checks
- [x] `alembic upgrade head` applied on a fresh volume via the `migrate` job
      (`claims`, `claim_documents`, `claim_images`, `agent_traces`, `eval_runs`,
      `policy_chunks`, `fraud_case_chunks` + HNSW cosine indexes)

Verified 2026-09-12: `curl http://localhost:8000/health` →
`{"status":"ok","checks":{"postgres":{"ok":true},"redis":{"ok":true}}}`.
Langfuse UI answered 200 at http://localhost:3000. Host Postgres is published
on **5434** because 5432 was already taken on this machine.

*(Compose checkboxes are filled after the first successful `docker compose up`
in this phase.)*

### Deferred (by design)

- LangGraph wiring, hybrid RAG, vision, real LLM calls
- Claim submit / trace / verdict HTTP handlers (registered, return 501)
- Frontend claim viewer
- Labeled eval set and published numbers (eval *set* is now held out in Phase 1; numbers still Phase 4)
- Frontend is not a Compose service yet (Langfuse occupies port 3000)

### Notes

- Repo lives at `/Users/abhishek-personal/projects/claimguard` because the
  original Cursor workspace home directory was not writable by this user.
- Langfuse v3 needs ClickHouse + MinIO + its own Postgres. Redis is shared;
  Celery is isolated on logical DB 1 so BullMQ and Celery do not collide.

---

## Phase 1 — Data layer: synthetic claims + corpora (2026-09-12)

**Goal:** a realistic-but-synthetic book of business, two RAG corpora, a
held-out labeled eval set, and a queryable hybrid index.

### Done

- 8 original policy specimens (PAP + HO-3): declarations, collision, OTC,
  exclusions, duties, dwelling, personal property, HO exclusions
- 16 rewritten fraud-pattern cases (Kaggle/NICB-style indicators, no copied rows)
- Frozen NOAA-shaped weather fixture (`data/weather/noaa_reference.json`)
  used for hail/wind grounding; live CDO is documented as opt-in
- `scripts/generate_synthetic_data.py`: 55 claims (37 dev / 18 eval),
  reportlab FNOL PDFs, EXIF-tagged placeholder photos (not CarDD),
  clean/messy/contradictory notes, ~20% injected fraud
  (duplicate VIN, weather mismatch, EXIF offset, mileage, inflated
  estimate, shared phone)
- Eval holdout in `data/eval_set/v0.jsonl` + `cases/`; **zero id overlap**
  with `data/synthetic_claims/`; `ground_truth` stripped from dev `claim.json`
- `scripts/ingest_corpora.py`: heading-aware 300–500 token chunks, overlap,
  `BAAI/bge-base-en-v1.5` via FastEmbed (768-d), pgvector + `rank_bm25` pickles
- `scripts/query_corpora.py` for raw dense + BM25 eyeballing
- Alembic `0002_emb_768` widens vector columns
- Tests for generation, holdout leakage, chunking, BM25, weather fixture

### Acceptance

- [x] `uv run pytest` — 26 passed
- [x] Synthetic claims: 37 dev folders with PDF + 73 photos + notes;
      18 eval cases labeled in `v0.jsonl` (4 fraud / 14 legit)
- [x] Corpora queryable: 46 policy chunks + 16 fraud chunks in pgvector
- [x] Eyeball search (2026-09-12):
      - "Is hail covered under other than collision?" → `pap-cg-01-part-d-otc` (dense 0.70)
      - "Is flood damage excluded on a homeowners policy?" → `ho3-cg-01-exclusions` Water/Flood
      - "same VIN appearing on two unrelated claims" → `fraud-04-duplicate-vin` (dense 0.77)
      - "hail claim with no NOAA storm event" → `fraud-05-weather-mismatch` (dense 0.78)
- [x] `GET /health` still 200 after migration + ingest

### Deferred

- LangGraph agents still stubbed
- Hybrid retriever (RRF + rerank) is the next wiring step
- Live NOAA refresh (`weather.refresh_from_noaa`)
- Committing generated PDFs/JPEGs is optional; regenerate with the seed-42 CLI

### How to re-run

```bash
uv run python scripts/generate_synthetic_data.py
uv run alembic upgrade head
uv run python scripts/ingest_corpora.py
uv run python scripts/query_corpora.py --corpus policy \
  --query "Is hail covered under other than collision?"
```

