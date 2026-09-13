# ClaimGuard

Multi-agent insurance **claims triage** and **fraud detection** — a portfolio
system built like a production service, not a notebook demo.

A claim submission (PDF forms, damage photos, adjuster notes) is ingested
asynchronously and scored by a LangGraph of specialized agents. The system
returns a structured verdict: severity, fraud risk with justification, missing
documents, policy coverage with cited clauses, and a draft settlement memo.
Low-confidence or high-fraud-risk claims go to a human review queue instead of
auto-resolving.

> **Data policy:** every claim, photo, and policy excerpt in this repo is
> synthetic or public/anonymized. There is no real PII and no real customer data.

## Architecture

```
                    ┌─────────────┐
   PDF / photos /   │  FastAPI    │  POST /v1/claims
   adjuster notes ─▶│  (enqueue)  │─────────┐
                    └─────────────┘         │
                                            ▼
                                      Redis (Celery)
                                            │
                                            ▼
                    ┌──────────────────────────────────────────┐
                    │              LangGraph worker            │
                    │                                          │
                    │   intake ─┬─ vision                      │
                    │           ├─ fraud  ─┐                   │
                    │           └─ policy ─┴─ adjudicator      │
                    │                         │                │
                    │              auto_resolve | human_review │
                    └──────────────────────────────────────────┘
                         │                │
            hybrid RAG   │                │  traces / cost
         (BM25+pgvector  │                ▼
          + RRF+rerank)  │           Langfuse
                         ▼
               Postgres + pgvector
            policy_chunks / fraud_case_chunks
```

*Diagram is the target topology. Phase 1 ships synthetic claims, policy/fraud
corpora, and a queryable pgvector + BM25 index. Agents are implemented next.*

## Quickstart

**Requirements:** Docker Desktop, [uv](https://docs.astral.sh/uv/), Python 3.12.

```bash
git clone <this-repo> claimguard
cd claimguard
cp .env.example .env

# Unit tests (no Docker)
uv sync --extra dev
uv run pytest

# Full local stack: pgvector, Redis, Langfuse, API, worker
docker compose up --build
curl -s http://localhost:8000/health

# Phase 1 data (synthetic claims + corpora)
uv run python scripts/generate_synthetic_data.py
uv run alembic upgrade head
uv run python scripts/ingest_corpora.py
uv run python scripts/query_corpora.py --corpus policy \
  --query "Is hail covered under other than collision?"
```

| Service          | URL                          | Notes                                      |
|------------------|------------------------------|--------------------------------------------|
| API              | http://localhost:8000        | OpenAPI at `/docs`                         |
| API health       | http://localhost:8000/health | 200 only if Postgres + Redis are up        |
| ClaimGuard Postgres | localhost:5434            | Host 5434 → container 5432 (avoids local Postgres) |
| Redis            | localhost:6379               | Celery uses logical DB 1                   |
| Langfuse         | http://localhost:3000        | `dev@claimguard.local` / `claimguarddev`   |
| Frontend (later) | http://localhost:3001        | Next.js; not in Compose yet                |

Langfuse is adapted from their [official Compose file](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml).
ClaimGuard owns the pgvector Postgres instance; Langfuse gets its own
`langfuse-db` plus ClickHouse and MinIO. Redis is shared (Celery uses logical DB 1).

## Eval results

| Metric                 | Value | Dataset | Notes                          |
|------------------------|-------|---------|--------------------------------|
| Fraud precision        | —     | —       | Phase 4 harness                |
| Fraud recall           | —     | —       | Phase 4 harness                |
| Retrieval groundedness | —     | —       | Phase 4 harness                |
| Hallucination rate     | —     | —       | Phase 4 harness                |
| Latency p50 / p95      | —     | —       | Phase 4 harness                |
| Cost per claim (USD)   | —     | —       | Phase 4 harness                |

Numbers will be written by `uv run claimguard-eval` into `eval_runs/` and
copied here. "I eyeballed 10 outputs" is not an eval story.

## Tech stack

| Layer            | Choice                                                                 |
|------------------|------------------------------------------------------------------------|
| Orchestration    | LangGraph StateGraph (conditional routing, not a chain)                |
| Retrieval        | BM25 + pgvector dense + RRF + cross-encoder rerank                     |
| Serving          | FastAPI + Celery + Redis                                               |
| Persistence      | Postgres 16 + pgvector, Alembic migrations                             |
| Observability    | Self-hosted Langfuse, PII redaction before logs, per-agent cost        |
| Schemas          | Pydantic v2, `extra="forbid"`, at every agent boundary                 |
| Eval             | Versioned labeled set, deterministic metrics + LLM-as-judge            |
| Frontend         | Next.js 15 (agent-trace dashboard)                                     |
| Packaging        | uv, Docker Compose                                                     |

## Why this project

I am a mid-level software engineer moving into AI engineering. Hiring managers
in that lane care as much about **contracts, tests, eval, and operations** as
they do about calling an LLM.

ClaimGuard is designed so a senior engineer can review it like a PR:

- typed boundaries instead of free-text handoffs
- hybrid retrieval instead of "embed it and hope"
- an eval harness that produces numbers you can regress against
- async workers, because a multi-agent claim run is not a 200ms HTTP handler
- no real customer data, ever

See [PROGRESS.md](PROGRESS.md) for the phase-by-phase build log.
