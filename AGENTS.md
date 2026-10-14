# AGENTS.md: instructions for AI coding agents (Codex, Claude Code, etc.)

Read this whole file before changing anything.

## What this project is
Antarctica is a website speed auditor on Google Cloud.
1. `POST /scans` (API, Cloud Run) saves a scan row and publishes a job to **Pub/Sub**.
2. Pub/Sub **pushes** the job to the **scanner** (Cloud Run), which runs **Lighthouse** and stores metrics and findings in **Postgres (Neon)**. Failed scans retry, and after 5 attempts they go to a dead-letter topic.
3. `GET /scans/{id}/fixes` asks **Gemini (Vertex AI)** for a concrete code fix per finding, grounded with **RAG** over web-performance docs stored in **pgvector**.
4. `core/evals` measures the accepted-fix rate **with vs. without RAG**, plus p95 latency, tokens/sec, and cost per request.

## Layout
```
services/api/        FastAPI: scans, reports, AI fixes
services/scanner/    Lighthouse runner, parser, Pub/Sub push worker
services/common/     config, models, store (Postgres + in-memory), queue
core/llm.py          Embedder/LLM interfaces: Vertex implementations + test fakes
core/rag/            chunking, embedding, pgvector retrieval
core/fixes/          fix suggestion prompt + parsing
core/evals/          eval harness (with vs. without RAG)
scripts/             fetch + ingest docs
db/migrations/       SQL, numbered; never edit an applied one
infra/               gcloud setup/deploy scripts (owner runs them)
docs/                DECISIONS.md (why), TASKS.md (what's next), SETUP.md (how)
```

## Hard rules
1. **Never commit secrets.** No keys, tokens, `.env`, or connection strings. Config comes from env vars.
2. **Never run commands that create, delete, or deploy cloud resources.** Write scripts; the owner runs them.
3. `ruff check .` and `python -m pytest -q` must pass before every PR. Tests must not hit the network or GCP. Use the fakes in `core/llm.py`, `InMemoryStore`, and `InMemoryPublisher`.
4. **One task per PR**, kept small. The PR description must say *what changed, why, how it was tested, and anything the owner must do manually*.
5. **Explain as you go.** The owner is learning from this codebase. Any new module starts with a short docstring explaining *how it works* and *why this design*, in the style of the existing files.
6. Don't change the eval methodology (`core/evals`) or the meaning of reported metrics without saying so explicitly in the PR. Those numbers go on a resume.
7. If something is ambiguous, open a draft PR with questions instead of guessing.

## Conventions
- Type hints everywhere; pydantic models at API boundaries.
- Timing with `time.perf_counter()`, stored in milliseconds.
- New behavior = new test. Data transforms always get a unit test.
- New schema changes = new migration file (`002_...sql`).

## Commands
```
pip install -e ".[dev,ai]"
ruff check .
python -m pytest -q
uvicorn services.api.main:app --reload          # local API, in-memory store
```
