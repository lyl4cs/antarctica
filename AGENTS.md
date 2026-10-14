# AGENTS.md: instructions for AI coding agents (Codex, Claude Code, etc.)

Read this whole file before you change anything.

## What this project is
Antarctica is a website performance auditor that runs on Google Cloud.
1. A user (or a GitHub Action) submits a URL.
2. The **API** queues a scan job on **Pub/Sub**.
3. The **scanner** worker (Cloud Run) runs Lighthouse, parses the metrics, and stores them in **Cloud SQL (Postgres + pgvector)**.
4. **AI agents** (Google ADK + Gemini on Vertex AI) diagnose the problems. They use **RAG** over performance docs and past audits, then propose code-level fixes.
5. **Evals** measure whether the fixes are correct, and record latency and cost.

## Stack
- Python 3.12, FastAPI, pydantic v2, psycopg 3, pgvector
- GCP: Cloud Run (services and jobs), Pub/Sub, Cloud SQL (Postgres 16), Vertex AI, Artifact Registry
- Lighthouse CLI (Node) inside the scanner container
- pytest and ruff

## Layout
```
services/api/       FastAPI: submit scans and read results      (agents OK)
services/scanner/   Lighthouse runner and result parser          (agents OK)
db/migrations/      SQL migrations, numbered 001_, 002_, ...     (agents OK)
infra/              gcloud setup and deploy scripts              (agents OK)
.github/            CI and the GitHub Action                     (agents OK)
core/rag/           retrieval and chunking                       ** OWNER ONLY **
core/agents/        ADK agent loop and self-reflection           ** OWNER ONLY **
core/evals/         eval set and metrics                         ** OWNER ONLY **
```

## Hard rules
1. **Do NOT write implementation code in `core/rag/`, `core/agents/`, or `core/evals/`.** The owner writes these himself. You MAY add tests that call their public interfaces, or fix an obvious import or typo there, and you must say so in the PR.
2. **Never commit secrets.** No keys, tokens, or `.env`. Configuration comes from environment variables (see `.env.example`).
3. **Never run commands that create or delete cloud resources** (`gcloud ... create/delete/deploy`, `terraform apply`). You can write scripts that do this, but the owner runs them.
4. Before opening a PR, `ruff check .` and `python -m pytest` must both pass.
5. Keep PRs small: one task per PR. In the PR description, say what changed, how you tested it, and anything the owner has to do by hand.
6. If a task is ambiguous, open a draft PR with your questions instead of guessing.

## Conventions
- Type hints everywhere. Use pydantic models at service boundaries.
- Measure all timing with `time.perf_counter()` and store it in milliseconds.
- Add a small test for every new function that parses or transforms data.
- SQL lives in `db/migrations/`. Never edit an existing migration; add a new one.

## Commands
```
pip install -e ".[dev]"
ruff check .
python -m pytest -q
```
