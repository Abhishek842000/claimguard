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
- Labeled eval set and published numbers
- Frontend is not a Compose service yet (Langfuse occupies port 3000)

### Notes

- Repo lives at `/Users/abhishek-personal/projects/claimguard` because the
  original Cursor workspace home directory was not writable by this user.
- Langfuse v3 needs ClickHouse + MinIO + its own Postgres. Redis is shared;
  Celery is isolated on logical DB 1 so BullMQ and Celery do not collide.
