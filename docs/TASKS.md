# Task board

Agent tasks are written so you can paste each one straight into Codex or Claude Code (web).
Each one fits in a single small PR. Do them **in order**, because later tasks depend on earlier ones.

---

## Agent tasks

### T1: Local dev environment
> Read AGENTS.md first. Add a `docker-compose.yml` that runs Postgres 16 with pgvector (image `pgvector/pgvector:pg16`) and applies `db/migrations/*.sql` on startup. Add a `Makefile` with targets `dev-db`, `test`, `lint`, and `api` (uvicorn services.api.main:app --reload). Update the README "Run locally" section. Done when `make dev-db && make test` works on a clean machine.

### T2: API backed by Postgres and Pub/Sub
> Read AGENTS.md first. In `services/api/main.py`, replace the in-memory `_SCANS` dict with Postgres (psycopg 3, `DATABASE_URL`), using the `scans` table in `db/migrations/001_init.sql`. On `POST /scans`, insert the row, then publish `{"scan_id","url"}` to the Pub/Sub topic in `SCAN_TOPIC`. Put the publisher behind a small interface so tests use a fake. Add `GET /scans/{id}/report`, which returns the audit metrics and findings once status='done'. Keep the existing tests passing and add tests that run against the docker-compose DB. Done when tests pass and the README shows a curl example.

### T3: Scanner worker
> Read AGENTS.md first. Implement `services/scanner/worker.py` following the contract in its docstring: Pub/Sub streaming pull on `SCAN_SUBSCRIPTION`, run `run_scan`, write `audits` and `findings` rows in one transaction, update the scan's status, attempts, duration_ms, and finished_at, and ack only after commit. After 3 failed attempts set status='failed'. Test the DB write path with a fixture report (don't run real Lighthouse in tests). Done when tests pass.

### T4: Deploy scripts (owner runs them)
> Read AGENTS.md first. Write `infra/deploy_api.sh` and `infra/deploy_scanner.sh`. They build with Cloud Build into Artifact Registry `antarctica`, deploy the API as a Cloud Run **service** and the scanner as a Cloud Run **service** with min-instances=0 and a Pub/Sub push or pull setup (explain which one you chose in the PR). Read PROJECT_ID and REGION from env. Use Cloud SQL connector settings (`--add-cloudsql-instances`). Do NOT run them. Done when `bash -n` passes and the PR lists the exact commands for the owner.

### T5: Docs ingestion pipeline (data only, no retrieval logic)
> Read AGENTS.md first. Create `scripts/fetch_docs.py`, which downloads about 40 web.dev and developer.chrome.com articles on Core Web Vitals and Lighthouse audits (put the URL list in `scripts/doc_urls.txt`), strips them to clean text, and saves them to `data/docs/<slug>.md` with the source URL at the top. Do NOT chunk or embed (the owner does that in core/rag). Done when the script runs and produces clean markdown.

### T6: GitHub Action
> Read AGENTS.md first. Create a composite GitHub Action in `action/` (`action.yml`). It takes inputs `api_url` and `target_url`, calls `POST /scans`, polls until done, and comments the performance score plus the top 3 findings on the PR. Fail the check if the score drops more than a configurable threshold compared with the last scan of the same URL (add an API endpoint for "last scan for URL" if you need one). Done when it works against a local API in a test workflow.

---

## Owner tasks (you, no agents)

- **O1: GCP setup.** Create the project, set a $20 budget alert, run `infra/setup_gcp.sh`.
- **O2: Read every agent PR before merging.** If you can't explain a line, ask the agent or me.
- **O3: RAG.** Chunking, embeddings (Vertex), pgvector retrieval in `core/rag/retrieve.py`. Answer the 5 questions at the top of the file first.
- **O4: Agents.** ADK planner → diagnoser → fixer with self-reflection in `core/agents/pipeline.py`.
- **O5: Eval set.** 30+ real cases in `core/evals/cases.jsonl` (scan Orland Park, Novus, and public sites).
- **O6: Measure.** Accepted-fix rate with and without RAG, tokens/sec, p95, and cost per audit. These fill the resume.
- **O7: Discovery.** Talk to the Orland Park web team and Novus about what they'd want fixed. Write notes in `docs/discovery.md`.
- **O8: Deploy** (run T4's scripts) and get one real fix live on a real site, so you have a before/after Lighthouse number.
