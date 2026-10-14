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
python -m pytest -q                         # 18 offline tests
uvicorn services.api.main:app --reload      # in-memory store + queue
```

## Deploy
See [docs/SETUP.md](docs/SETUP.md). Design decisions and tradeoffs: [docs/DECISIONS.md](docs/DECISIONS.md).

## Layout
`services/` (API, scanner worker, shared store/queue) · `core/` (LLM clients, RAG, fix suggester, evals) · `infra/` (gcloud scripts) · `db/migrations/` · `scripts/` (doc fetch/ingest)
