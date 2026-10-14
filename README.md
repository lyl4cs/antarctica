# Antarctica

**A website speed auditor with AI fix suggestions, on Google Cloud.** Submit a URL. Antarctica runs Lighthouse on a queue of Cloud Run workers, stores the results in Postgres, and uses Gemini with retrieval over web-performance docs (RAG on pgvector) to suggest concrete code fixes for each problem. An eval harness measures whether RAG actually improves those fixes.

```
client ──POST /scans──▶ API (Cloud Run) ──publish──▶ Pub/Sub "scans"
                          │                              │ push (retry w/ backoff, DLQ after 5)
                          │                              ▼
                          │                     Scanner (Cloud Run, Lighthouse)
                          ▼                              │
                    Postgres (Neon) ◀────────────────────┘   scans · audits · findings
                    + pgvector       ◀── RAG ── doc_chunks (web.dev + Chrome docs, Vertex embeddings)
                          │
              GET /scans/{id}/fixes ──▶ Gemini (Vertex AI) ──▶ fix + code, grounded in sources
                          │
                 core/evals: accepted-fix rate with vs. without RAG · p95 · tokens/s · $/request
```

## Run locally (no cloud needed)
```bash
pip install -e ".[dev,ai]"
python -m pytest -q                         # 33 offline tests (DB tests skip)
uvicorn services.api.main:app --reload      # in-memory store + queue
```

Integration tests against real Postgres + pgvector (CI runs these in a separate job):
```bash
docker compose up -d
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/antarctica_test
python -m pytest tests/integration -q
```

## Frontend
A React + TypeScript app in [`frontend/`](frontend/) (Vite, hosted on Vercel), built from the Claude Design files in [`docs/design/`](docs/design/). Start a scan, watch it run, read the report and ask for AI fixes, and compare any two scans of a site over time. It polls the API every 2 s while a scan runs.
```bash
uvicorn services.api.main:app --reload --port 8000   # terminal 1
cd frontend && npm ci && npm run dev                  # terminal 2 -> http://localhost:5173
```
Deploying to Vercel, and why it's a separate app instead of being served by FastAPI: [frontend/README.md](frontend/README.md), ADR 014.

The API still serves the older single-file UI at `/` (`services/api/static/index.html`); it is kept as a no-build fallback and is covered by a test.

## GitHub Action: perf check on every PR
Scans your preview deploy, comments the score + top 3 fixes on the PR (one comment, updated on re-runs), and fails if the score drops more than `threshold` points below the baseline.
```yaml
# .github/workflows/perf.yml in the repo you want checked
on: pull_request
permissions: { pull-requests: write }
jobs:
  perf:
    runs-on: ubuntu-latest
    steps:
      - uses: lyl4cs/antarctica/action@main
        with:
          api-url: https://<your-antarctica-api>
          url: https://<preview-url-for-this-pr>
          baseline-url: https://<your-production-site>   # optional, defaults to url
          threshold: 5                                   # optional
```
Outputs: `score`, `baseline`, `passed`. Logic lives in `scripts/pr_check.py` (stdlib only, unit-tested).

## MCP server: use it from Claude / Cursor
`antarctica-mcp` exposes `run_audit`, `get_report`, `suggest_fixes`, `site_history` as MCP tools over stdio. Setup for Claude Desktop and Claude Code: [docs/MCP.md](docs/MCP.md).

## Deploy
See [docs/SETUP.md](docs/SETUP.md). Design decisions and tradeoffs: [docs/DECISIONS.md](docs/DECISIONS.md).

## Layout
`services/` (API, scanner worker, shared store/queue) · `core/` (LLM clients, RAG, fix suggester, evals) · `frontend/` (React app, Vercel) · `mcp_server/` (MCP tools) · `infra/` (gcloud scripts) · `db/migrations/` · `scripts/` (doc fetch/ingest) · `docs/design/` (approved UI designs)
