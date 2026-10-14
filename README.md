# Antarctica

**An AI performance auditor for the web, on Google Cloud.** Point it at a URL and it runs Lighthouse, finds what's slowing the page down, and uses a multi-agent system (Google ADK + Gemini) with retrieval over web-performance docs to propose code-level fixes. It also measures whether those fixes are right.

```
          ┌──────────┐   POST /scans   ┌────────────┐  publish  ┌─────────┐
 user /   │ GitHub   │ ──────────────▶ │  API       │ ────────▶ │ Pub/Sub │
 PR ────▶ │ Action   │                 │ Cloud Run  │           │ "scans" │
          └──────────┘                 └─────┬──────┘           └────┬────┘
                                             │ read                  │ pull
                                             ▼                       ▼
                                    ┌──────────────────┐     ┌──────────────┐
                                    │ Cloud SQL        │◀────│ Scanner      │
                                    │ Postgres+pgvector│     │ Lighthouse   │
                                    └────────┬─────────┘     │ Cloud Run    │
                                             │ RAG           └──────────────┘
                                             ▼
                                    ┌──────────────────┐
                                    │ ADK agents       │  planner → diagnoser → fixer
                                    │ Gemini on Vertex │  (ReAct + self-reflection)
                                    └────────┬─────────┘
                                             ▼
                                    evals: accuracy · tokens/sec · p95 · $/audit
```

## Status
Early build. See `docs/ROADMAP.md` and `docs/TASKS.md`.

## Run locally
```bash
pip install -e ".[dev]"
python -m pytest -q
uvicorn services.api.main:app --reload       # API on :8000
python -m services.scanner.run_lighthouse https://example.com   # needs: npm i -g lighthouse
```

## Layout
- `services/api`: FastAPI service
- `services/scanner`: Lighthouse runner, parser, and worker
- `core/rag`, `core/agents`, `core/evals`: the AI system
- `db/migrations`: Postgres schema (pgvector)
- `infra`: GCP setup and deploy scripts
