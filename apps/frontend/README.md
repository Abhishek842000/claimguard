# ClaimGuard frontend

Next.js 15 App Router dashboard on **port 3001** (Langfuse keeps 3000).

```bash
npm install
npm run dev
```

The browser talks only to `/api/claimguard/*`. That route attaches
`X-API-Key` and proxies to FastAPI so the key never sits in client JS.

| Page | What it shows |
|------|----------------|
| `/` | Submit (sample folder or file upload), claims list, cost panel |
| `/claims/[id]` | Verdict + visual agent timeline (not a JSON dump) |

Set `CLAIMGUARD_API_URL` / `CLAIMGUARD_API_KEY` if the API is not on
`http://127.0.0.1:8000` with the local default key.
