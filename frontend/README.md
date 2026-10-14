# Antarctica frontend

The web app for Antarctica: React + TypeScript, built with Vite, hosted on Vercel. It is a pure client of the API in `services/api`: everything it shows comes from the API, and it has no backend of its own.

The look comes from the approved Claude Design files in [`docs/design/`](../docs/design/). Open them in a browser next to the running app to compare.

## How it works

### Routes
| Path | Page | API calls |
|---|---|---|
| `/` | Start a scan, recent scans | `POST /scans`, `GET /scans?limit=6` |
| `/scans/:id` | Live status: queued, running, ready, failed | `GET /scans/{id}` every 2 s until it's done or failed; Retry is a new `POST /scans` |
| `/scans/:id/report` | Score, 5 core metrics, findings, AI fixes | `GET /scans/{id}/report`, `GET /scans/{id}/fixes?limit=N` |
| `/history?url=…` | Score chart, before/after diff, all scans | `GET /sites/scans?url=…`, plus `GET /scans/{id}/report` for the two scans being compared |

React Router maps paths to pages in the browser. Vercel serves `index.html` for every path (`vercel.json` rewrites), so deep links and reloads work.

### The API client (`src/api.ts`)
One module makes every request. Its TypeScript types copy the pydantic models (`services/common/models.py`, `FixOut` in `services/api/main.py`), so a backend field rename means changing this one file, and `npm run typecheck` then lists every screen that used the old name. Errors become an `ApiError` with the HTTP status, and pages branch on it:
- `404`: unknown scan id → "not found"
- `409` from `/report` or `/fixes`: the scan isn't done → redirect to the scan page, which polls
- `503` from `/fixes`: the server has no AI configured → a calm inline note, not an error
- status `0`: the request never got an answer (API down, CORS, offline)

### Polling, not WebSockets
A scan takes 30–60 s and changes state about three times (queued → running → done or failed). The scan page asks every 2 seconds and stops as soon as the scan finishes, or when you leave the page. That's roughly 30 small GETs per scan. A WebSocket or Server-Sent Events channel would need a held-open connection per viewer on Cloud Run (billed per request-second, with timeouts to manage) and state on a stateless API, to deliver three updates. Push becomes worth it for many fast updates. See ADR 014 in [`docs/DECISIONS.md`](../docs/DECISIONS.md).

### AI fixes are fetched lazily
`GET /scans/{id}/fixes?limit=N` returns fixes for the top N findings, in order. To get the fix for the finding at index `i`, the page asks for `limit = i + 1` (the API caps it at 10), then caches every fix in the response by index. Opening a finding above it later costs no request, and if a larger request is already running, a click waits for it instead of sending another. Each fix is a Gemini call with real latency and cost (both shown on the card), so nothing is generated until someone asks.

### Files
```
src/api.ts              typed API client (the only place that calls fetch)
src/App.tsx             route table
src/pages/              Home, ScanPage, ReportPage, HistoryPage, NotFound
src/components/         header/layout, penguin SVG illustrations, icons, states
src/lib/format.ts       number/date formatting, Lighthouse thresholds, deltas
src/lib/chart.ts        history chart geometry (hand-rolled SVG, no chart library)
src/lib/markdown.ts     safe parser for links/code in Lighthouse descriptions
src/lib/scanProgress.ts scan page view-model (steps, penguin mood, timer bars)
src/styles.css          one stylesheet; palette and fonts as CSS variables
```

## Run locally
Needs Node 22.12+ and the API running.
```bash
# terminal 1, repo root: API with the in-memory store (no cloud needed)
pip install -e ".[dev]"
uvicorn services.api.main:app --reload --port 8000

# terminal 2
cd frontend
cp .env.example .env        # VITE_API_URL=http://localhost:8000 (also the default)
npm ci
npm run dev                 # http://localhost:5173
```
The API allows CORS from `http://localhost:5173` by default (`CORS_ORIGINS`). With the in-memory store there's no scanner, so new scans stay queued. That's enough to click through, but reports need a real deployment or seeded data.

Checks (CI runs the same four):
```bash
npm run typecheck
npm test -- --run
npm run build
```

## Deploy to Vercel
1. vercel.com → **Add New → Project** → import `lyl4cs/antarctica`.
2. **Root Directory: `frontend`**. Vercel detects Vite; `vercel.json` sets the build command, output dir (`dist`) and the SPA rewrite.
3. **Environment Variables:** `VITE_API_URL` = your Cloud Run API URL (what `deploy.sh` prints, no trailing slash). Vite bakes it into the JavaScript at build time, so redeploy after changing it. It is public by design; never put secrets in `VITE_` variables.
4. Deploy and copy the production URL (e.g. `https://antarctica.vercel.app`).
5. Let that origin call the API: from the repo root,
   ```bash
   PROJECT_ID=<your-project> FRONTEND_ORIGIN=https://antarctica.vercel.app ./infra/deploy.sh
   ```
   Several origins are comma-separated: `FRONTEND_ORIGIN="https://antarctica.vercel.app,https://antarctica-git-main-you.vercel.app"`. Keep passing `FRONTEND_ORIGIN` on every later deploy, because `--set-env-vars` replaces the whole list and the API would fall back to allowing only localhost.

If the page loads but every request fails with status 0, it's almost always CORS: the browser console says "blocked by CORS policy", and the fix is step 5 with the exact origin shown there.
