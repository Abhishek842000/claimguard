# ClaimGuard frontend

Next.js 15 App Router dashboard. Dev server is pinned to **port 3001** so
self-hosted Langfuse can keep port 3000.

```bash
npm install
npm run dev
```

Phase 0 is a visual scaffold only. Claim submit + agent-trace views are wired
once `POST /v1/claims` and `GET /v1/claims/{id}/trace` exist.
