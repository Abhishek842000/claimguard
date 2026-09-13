# Deploy ClaimGuard (Fly.io primary, Railway alternative)

Target for a demo budget: **API + worker on Fly.io** (one image, two process
groups), **Fly Managed Postgres with pgvector**, **Upstash Redis**, and
**Langfuse Cloud Hobby**. Self-hosting Langfuse v3 means ClickHouse + MinIO +
a second Postgres — too many machines for a portfolio demo. Run that stack
locally via Compose; point production at Langfuse Cloud.

The same Docker image serves both processes (`Dockerfile`). `fly.toml` sets
the process commands.

---

## 0. Prerequisites

- [flyctl](https://fly.io/docs/flyctl/install/) signed in (`fly auth login`)
- A Fly org that can create apps in `ord` (or change `primary_region`)
- [Langfuse Cloud](https://cloud.langfuse.com) Hobby project (free tier)
- [Upstash Redis](https://upstash.com) free database (or Fly Redis if your org still has it)
- Optional: `OPENAI_API_KEY` if you want live LLM completions. The demo and
  `claimguard-eval` run offline with heuristic completers.

If the app name `claimguard` is taken, edit `app =` in `fly.toml` before launch.

---

## 1. Postgres with pgvector (Fly Managed Postgres)

```bash
fly mpg create --name claimguard-db --region ord --plan basic --pgvector
```

Wait until the cluster is ready, then attach it to the app (creates
`DATABASE_URL` as a secret). If the app does not exist yet, create it first
(step 3) and come back.

```bash
fly mpg attach claimguard-db -a claimguard
```

`claimguard.config.Settings` rewrites `postgres://` / `postgresql://` to
`postgresql+psycopg://` so SQLAlchemy uses the psycopg driver.

Confirm the `vector` extension is on in the app database (MPG `--pgvector`
should do this; run it anyway if `\dx` does not list `vector`):

```bash
fly mpg connect claimguard-db
-- then in psql:
CREATE EXTENSION IF NOT EXISTS vector;
\dx vector
\q
```

Alembic runs automatically on each deploy (`[deploy] release_command` in
`fly.toml`).

---

## 2. Redis (Celery broker)

Local Compose isolates Celery on logical Redis DB 1. Managed Redis is usually
**one database**. Use the same URL for health, broker, and results — Celery
prefixes its keys, so they do not collide with a ping.

Create an Upstash Redis database (TLS). Copy the Redis URL, then:

```bash
fly secrets set -a claimguard \
  REDIS_URL="rediss://default:...@....upstash.io:6379" \
  CELERY_BROKER_URL="rediss://default:...@....upstash.io:6379" \
  CELERY_RESULT_BACKEND="rediss://default:...@....upstash.io:6379"
```

---

## 3. Langfuse (Cloud Hobby, not self-hosted)

1. Create a project at https://cloud.langfuse.com
2. Settings → API Keys → create
3. Host is region-specific (`https://us.cloud.langfuse.com` or
   `https://cloud.langfuse.com` / EU). Use the host shown in the project settings.

```bash
fly secrets set -a claimguard \
  LANGFUSE_HOST="https://us.cloud.langfuse.com" \
  LANGFUSE_PUBLIC_KEY="pk-lf-..." \
  LANGFUSE_SECRET_KEY="sk-lf-..."
```

Traces are redacted through `pii_redaction.py` before ingest. Langfuse
failures are logged, not fatal.

**Self-host instead:** only if you already want the Compose Langfuse stack
(ClickHouse + MinIO + `langfuse-db`) on a box you pay for. Do not try to
replicate that topology on three extra Fly apps for this demo.

---

## 4. App secrets + first deploy

```bash
# From the repo root. --copy-config uses fly.toml as-is.
fly launch --no-deploy --copy-config --name claimguard

fly secrets set -a claimguard \
  APP_ENV=prod \
  CLAIMGUARD_API_KEY="$(openssl rand -hex 24)" \
  RATE_LIMIT_PER_MINUTE=60

# Optional live LLM path
fly secrets set -a claimguard OPENAI_API_KEY="sk-..."

# Attach DB if you skipped it earlier
fly mpg attach claimguard-db -a claimguard

fly deploy
```

`fly.toml` starts:

| Process | Command | Memory |
|---------|---------|--------|
| `api` | `uvicorn apps.api.main:app --host 0.0.0.0 --port 8080` | 1 GB |
| `worker` | Celery `-Q claims` concurrency 2 | 2 GB |

Health checks hit `GET /health` (Postgres + Redis). The check fails until
both attachments exist.

```bash
fly status -a claimguard
fly logs -a claimguard
curl -sS "https://claimguard.fly.dev/health"
```

Expect `{"status":"ok",...}`. `/v1` routes need `X-API-Key`.

---

## 5. Ingest policy + fraud corpora (once)

The image includes `data/` and `scripts/`. First ingest downloads
`BAAI/bge-base-en-v1.5` via FastEmbed (~300 MB). Run it on the worker
machine (2 GB):

```bash
fly ssh console -a claimguard --process-group worker \
  -C "python scripts/ingest_corpora.py"
```

Re-run only after changing `data/policy_docs` or `data/fraud_corpus`.

---

## 6. Smoke a claim

```bash
API="https://claimguard.fly.dev"
KEY="the CLAIMGUARD_API_KEY you set"

curl -sS -X POST "$API/v1/claims" \
  -H "content-type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"source_dir":"data/synthetic_claims/09d919dc-2168-544f-8ec0-4a0f018c8ef6"}'

# poll
curl -sS -H "X-API-Key: $KEY" "$API/v1/claims/<claim_id>"
```

Dashboard against a remote API (local Next.js is fine for the demo):

```bash
cd apps/frontend
CLAIMGUARD_API_URL="https://claimguard.fly.dev" \
CLAIMGUARD_API_KEY="$KEY" \
npm install && npm run dev
# http://localhost:3001
```

---

## Railway alternative (same image, two services)

Use this if you already have a Railway account and do not want Fly.

1. **New project** → empty.
2. **Postgres.** Railway Postgres 16. In the Query tab:

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Redis.** Add the Railway Redis plugin.
4. **API service** → Deploy from GitHub, Dockerfile.
   - Start command override:  
     `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`
   - Variables:
     - `DATABASE_URL` = Railway Postgres URL (the `postgres://` rewrite applies)
     - `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` = Redis URL
     - `CLAIMGUARD_API_KEY`, `LANGFUSE_*`, `APP_ENV=prod`
5. **Worker service** → same repo / same image.
   - Start command:  
     `celery -A apps.worker.celery_app:celery_app worker --loglevel=INFO --concurrency=2 -Q claims`
   - Share the same variables as the API.
6. One-off migrate + ingest from the API service shell:

   ```bash
   alembic upgrade head
   python scripts/ingest_corpora.py
   ```

7. Public URL is the API service. Health: `GET /health`.

---

## Cost notes (demo)

| Piece | Suggested plan | Why |
|-------|----------------|-----|
| Fly API | shared-cpu-1x, 1 GB, `min_machines_running = 1` | Health + enqueue |
| Fly worker | shared-cpu-1x, 2 GB | FastEmbed ingest + graph |
| Fly MPG | `basic` + `--pgvector` | Claims, traces, 768-d chunks |
| Upstash Redis | free | Celery broker |
| Langfuse Cloud | Hobby | Avoid ClickHouse/MinIO on Fly |
| OpenAI | omit | Offline heuristics are enough to demo |

Scale the worker to zero only if you accept cold queue lag; `auto_stop` is
on for the API HTTP process only.

---

## Tear down

```bash
fly apps destroy claimguard
# delete the MPG cluster from the Fly dashboard if you created claimguard-db
```
