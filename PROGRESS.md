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

---

## Phase 2 — LangGraph backbone (in progress, 2026-09-12)

**Goal:** `ClaimState` as the typed graph contract, plus a compiled StateGraph
with parallel specialists and deterministic routing.

### Done

- `ClaimState` TypedDict: `claim_id`, raw docs/images, intake / damage /
  fraud / policy / verdict, `trace`, `requires_human_review`, `error`
- `DocumentRef`, `ImageRef`, `AgentStep` as the pre-intake / trace types
- `StateGraph`: `intake_agent` → parallel (`vision_agent`, `fraud_agent`,
  `policy_agent`) → `adjudicator_agent` → `route_to_human` | `auto_resolve`
- Hard gates: human review if `confidence < 0.65` OR `fraud_score > 0.45`
  (fail closed on missing verdict or `error`)
- `trace` uses `operator.add` so parallel nodes cannot clobber each other
- Agents still raise `NotImplementedError`; tests inject stub node bodies

### Deferred

- Real vision / fraud / policy / adjudicator implementations
- Persist verdict + trace from the Celery worker

---

## Phase 3 — Agents (in progress, 2026-09-12)

**Goal:** one agent at a time. Schema → versioned prompt → function → mocked
unit tests → standalone sample inspect. Do not start the next agent until
this loop is green.

### Intake — done

- Input: `IntakeAgentInput` (from `ClaimState` or a claim folder)
- LLM schema: `IntakeExtraction` (model cannot invent storage URIs)
- Output: `ClaimIntake`
- Prompt: `claimguard/llm/prompts/intake_v1.yaml` (`schema: IntakeExtraction`)
- `generate_structured`: validate → feed ValidationError back → bounded retry
  → exhaust sets `error` + `requires_human_review` (Instructor-style, vendor-neutral)
- PDF: pypdf text-native; OCR protocol fallback (`OcrBackend`)
- NER: `RegexEntityExtractor` default; `HuggingFaceNerExtractor` is a swap-in
- Offline path: `HeuristicIntakeCompleter` so a sample claim runs without an API key
- Tests: happy path, malformed-triggers-retry, exhaust-flags-review, sample FNOL parse
- Standalone: `uv run python scripts/run_intake_sample.py`

### Next

- Vision / fraud / policy / adjudicator (wired in the following section)

---

## Phase 4 — Graph wiring, worker, API, Langfuse (2026-09-12)

**Goal:** a synthetic claim can be POSTed, processed asynchronously, and
retrieved with a full verdict + trace that also lands in Langfuse.

### Done

- All five agents run in the compiled StateGraph:
  `intake → parallel(vision, fraud, policy) → adjudicator → route`
- `AgentStep` now carries redacted input/output snapshots, latency, tokens,
  cost, prompt version, and model
- Graph-level guard: any throw or exhausted structured-output retry sets
  `error` + `requires_human_review` and the claim still finishes
- Vision: `DamageClassifier` protocol; default is filename/caption heuristic
  (swap in a fine-tuned HF model later without touching the node)
- Fraud: hybrid RAG (BM25 + dense + RRF) + NOAA/police/VIN rules + LLM
  synthesis (`fraud_v1`)
- Policy: hybrid RAG + `filter_grounded_clauses` so hallucinated clause IDs
  are dropped programmatically (`policy_v1`)
- Adjudicator: `adjudicator_v1` drafts `SettlementMemo`; routing scores stay
  as tunable constants in `RoutingThresholds`
- Langfuse: real HTTP ingest to `/api/public/ingestion` (per-agent span +
  generation with tokens/cost). Failure is logged, not fatal
- `POST /v1/claims` `{source_dir}` → 202 + Celery `process_claim`
- Worker loads artifacts, `invoke_claim_pipeline`, writes verdict + traces
- `GET /v1/claims/{id}` returns status, verdict, redacted trace

### Choices + tradeoffs

- Reranker is identity/RRF, not a cross-encoder — keeps the worker image
  small; `Reranker` protocol is the swap-in
- Vision default is heuristic, not a downloaded HF checkpoint — same reason
- Offline heuristic completers so the pipeline runs without `OPENAI_API_KEY`
- Queue remains Celery+Redis (already in the stack)

### Tested

- `uv run pytest` — 58 passed (mocked LLM retry, citation grounding,
  exception → human review, full sample-claim graph, API enqueue)

### How to demo

```bash
# Stop the stale Compose api/worker so local code owns :8000 and the queue
docker compose stop api worker
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
uv run celery -A apps.worker.celery_app:celery_app worker -Q claims -l info
curl -sS -X POST http://127.0.0.1:8000/v1/claims \
  -H 'content-type: application/json' \
  -d '{"source_dir":"data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6"}'
# poll GET /v1/claims/{id} then open Langfuse at http://localhost:3000
```

### Deferred

- HF vision + cross-encoder rerank
- Docker image rebuild so Compose api/worker pick up Phase 4+ code
  (`./data` is now mounted)
- Frontend was still a scaffold (done in Phase 5)

---

## Phase 5 — Dashboard, PII enforcement, cost, API auth (2026-09-12)

**Goal:** submit a claim in the UI, watch it process, and read a visual
agent trace — with PII actually stripped from logs/Langfuse, cost rolled
up for interview talking points, and a production-shaped API gate.

### Done

- Next.js dashboard on **3001**:
  - submit a sample folder **or** upload docs/images + notes
  - claims list with status
  - detail page: verdict + timeline (agent → key output → confidence/latency/cost)
  - cost panel: running total, avg/claim, breakdown by agent
  - BFF at `/api/claimguard/*` attaches `X-API-Key` (key stays server-side)
- `pii_redaction.py` now also masks DOB-like dates and is a required
  structlog + stdlib logging filter. Langfuse `flush()` redacts the batch
  again before HTTP. Unit test asserts SSN / DOB never appear in rendered
  log output
- `cost_tracker.py` `summarize()` + `GET /v1/metrics` (Postgres
  `agent_traces` is the source of truth — API and worker do not share
  memory)
- API key (`X-API-Key` / Bearer) + in-process sliding-window rate limit
  on `/v1`. `/health` and `/docs` stay open
- `GET /v1/claims`, `GET /v1/claims/samples`, `POST /v1/claims/upload`
- Re-submitting the same sample folder mints new claim + document ids

### Choices + tradeoffs

- Auth is a shared-secret stub, not OAuth/JWT — enough to show the API
  is not anonymously writable; swap for an IdP later
- Rate limiter is in-memory per API process (Compose runs one replica)
- Cost numbers come from persisted traces, not a process-global ledger
- Reranker remains identity/RRF; vision remains filename heuristic
- Frontend is not a Compose service (Langfuse occupies 3000)

### Tested

- `uv run pytest` — **70 passed**
  - PII: SSN/DOB never in structlog or stdlib log output; Langfuse
    payload redacted
  - Cost aggregation (total / avg / by agent)
  - API key 401, rate-limit 429, list/upload/samples
  - Identity reranker keeps RRF order
  - Existing agent + retrieval tests still green (mocked LLM)
- Live: submitted Phoenix hail (`PA-2026-000039`) from the UI →
  `needs_review`, fraud 0.59, confidence 0.62, 6-step visual timeline
  (intake / fraud weather-mismatch / policy covered / vision dent /
  adjudicator / human review). Cost panel showed $0.001183 total

### How to demo

```bash
docker compose stop api worker   # if stale images own :8000
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
uv run celery -A apps.worker.celery_app:celery_app worker -Q claims -l info
cd apps/frontend && npm install && npm run dev
# open http://localhost:3001
```

### Deferred

- HF vision + cross-encoder rerank
- 90s mp4 in `docs/demo/` — record with QuickTime when publishing
- Compose service for the Next.js app
- JWT / per-user keys

---

## Phase 6 — Deploy docs, README, eval numbers (2026-09-12)

**Goal:** a stranger can clone, follow the README, get a local eval in under
15 minutes, and see real harness numbers behind every claim. Deploy path is
documented exactly (Fly primary, Railway alternative).

### Done

- Eval harness is real (`claimguard-eval`): 18-case v0 holdout, amount
  baseline vs ClaimGuard, planted-clause groundedness baseline, deterministic
  `judge_v1`. Artifact checked in: `eval_runs/v0.json` / `eval_runs/v0.md`
- Fraud book-of-business rules: shared phone/email, duplicate VIN, EXIF
  offset (skip if incident year `< 2000`). **Bugfix:** `intake.claim_id` is a
  `UUID`; the index stores strings — self was counted as a peer and every
  claim looked "shared". Subtract `str(intake.claim_id)`
- `Settings` rewrites Fly/Railway `postgres://` → `postgresql+psycopg://`
- `fly.toml`: one image, `api` + `worker` process groups, `alembic upgrade`
  as `release_command`. Dockerfile copies `data/` + `scripts/` for ingest
- `docs/DEPLOY.md`: Fly MPG + `--pgvector`, Upstash Redis, Langfuse Cloud
  Hobby (self-host ClickHouse/MinIO called out as too heavy), Railway steps
- README: Mermaid architecture + LangGraph flow, 15-min `uv` path, eval
  before/after table, stack rationale, "What I'd do with more time"
- `RESUME_BULLETS.md` uses the harness numbers, not placeholders
- Regression: `tests/eval/test_published_v0.py` fails if README/resume drift
  from `eval_runs/v0.json`

### Holdout numbers (v0, 18 cases, 4 fraud / 14 legit)

| Metric | Baseline | ClaimGuard |
|--------|----------|------------|
| Fraud precision | 0.3333 (2 TP / 4 FP) | **1.0 (2 TP / 0 FP / 2 FN / 14 TN)** |
| Fraud recall | 0.5 | **0.5** |
| Groundedness | 0.0 | **1.0** |
| Hallucination | 1.0 | **0.0** |
| Latency p50 / p95 | 13.7 / 17.0 ms | same (offline heuristics) |
| Cost / claim | $0.001347 | same |

FN: mileage-inconsistency fire (`a6ca84e9-…`, score 0.12, no mileage rule);
duplicate-VIN collision (`c6ef8f61-…`, score 0.34, only `FR-MISSING-POLICE-REPORT`).
Do not claim recall improved.

### Choices + tradeoffs

- Eval retriever is in-memory keyword overlap over `data/policy_docs` +
  `data/fraud_corpus` markdown so `claimguard-eval` needs no Docker/pgvector
- Judge is deterministic (citation ⊆ retrieved), not a live LLM-as-judge
- Deploy default is Langfuse Cloud Hobby, not self-host, for machine count
- Managed Redis is one DB (vs Compose DB 0/1). Celery key prefixes isolate
- Reranker remains identity/RRF; vision remains filename heuristic

### Tested

- `uv run pytest` — **80+** (entity UUID subtraction, metrics, config URL
  rewrite, published-artifact lock)
- `uv run claimguard-eval --dataset v0 --out eval_runs` — table above
- Did **not** `fly deploy` from this machine (docs are the deliverable)

### Deferred

- Actual Fly/Railway machines (needs the user's Fly org + secrets)
- Checked-in `docs/demo/claimguard-demo.mp4`
- Mileage rule + tighter VIN graph (would target the 2 FN)
- Human-review → eval-set feedback loop

---

## Demo upload hardening (2026-09-13)

**Goal:** film a walkthrough with camera photos without the picker, rate
limit, or filename heuristic fighting the demo.

### Done

- File picker **appends** across opens; selected files are listed with Remove
- `docs/demo/README.md` filming recipe (stock/own photos, Phoenix FNOL, notes)
- Rate limit applies to **writes only** so list/metrics polls cannot 429 upload
- Vision reads intake notes + loss description, so `demo_img.webp` still
  labels dent when the text says hail
- `FR-NOTE-LOCATION-MISMATCH` when notes name a different known city than
  the FNOL form (Phoenix notes + Denver form)

### Tested

- `uv run pytest tests/unit/test_auth.py tests/unit/test_vision_agent.py tests/unit/test_fraud_agent.py`
- Live: leftover dashboard polls no longer 429 `POST /v1/claims/upload`

### Deferred

- Pixel-level hail classifier (still a text/filename heuristic)
- Checked-in `docs/demo/claimguard-demo.mp4`

