# Task board

## Done (MVP code, tested offline)
- API: create scan, status, report, AI fixes endpoint
- Scanner: Pub/Sub push worker, retries with an attempt cap, idempotent saves
- Store: Postgres (Neon) + in-memory; migrations runner
- RAG: chunking, Vertex embeddings, pgvector retrieval
- Fix suggester (Gemini, JSON output, token, latency, and cost tracking)
- Eval harness: with vs. without RAG, LLM judge, p95, tokens/sec, $/request
- Infra: setup + deploy scripts (Cloud Run, Pub/Sub push, DLQ, Secret Manager), Cloud Build
- Scan history endpoint (`GET /sites/scans`), before/after `scripts/measure.py` (median of N runs)
- Eval draft builder `scripts/build_cases.py`, minimal web UI at `/`
- 22 offline tests + CI
- 9 Postgres/pgvector integration tests (incl. concurrent-delivery lock test), own CI job

## Owner tasks (only you can do these)
1. GitHub repo, Neon, GCP project + **$20 budget alert**, `setup_gcp.sh`, `deploy.sh` (docs/SETUP.md)
2. Fetch + ingest docs
3. Build `core/evals/cases.jsonl`: 30+ real findings with correct reference fixes
4. Run the eval. Spot-check 10+ judge verdicts by hand
5. Apply fixes to Novus; measure Lighthouse before/after (median of 3 runs)
6. **Read every module docstring.** You'll be asked to explain this system in interviews

## Agent tasks: paste into Codex / Claude Code one at a time

### A1: Postgres integration tests ✅ DONE
> Read AGENTS.md first. Add `docker-compose.yml` with `pgvector/pgvector:pg16`, and integration tests for `PostgresStore` and `PgVectorStore` that run only when `TEST_DATABASE_URL` is set (skip otherwise). Apply migrations with `infra/migrate.py` in a fixture. Add a separate CI job using a Postgres service container. Done when the integration tests pass in CI.

### A2: Scan history + re-scan endpoint ✅ DONE
> Read AGENTS.md first. Add `GET /sites/scans?url=...` returning past scans for a URL (newest first) and their performance scores, so before/after comparisons are one call. Add a migration if needed. Tests with InMemoryStore. Done when tests pass.

### A3: Before/after measurement script ✅ DONE
> Read AGENTS.md first. Add `scripts/measure.py URL --runs 3 --api $API`. It submits N scans, waits for completion, and prints the median performance score, LCP, TBT, and CLS. Explain in the docstring why we use the median of several runs (Lighthouse variance). Mock HTTP in tests.

### A4: Eval case builder ✅ DONE
> Read AGENTS.md first. Add `scripts/build_cases.py`. It takes scan IDs, pulls their findings via the API, and writes a draft `cases.jsonl` with `reference_fix` left empty for the owner to fill in. Deduplicate by audit_id per URL. Tests with a fake API.

### A5: Minimal web UI ✅ DONE
> Read AGENTS.md first. Add a single static page served by the API at `/`: URL input → submit → polls status → shows score, top findings, and fix suggestions. Plain HTML + vanilla JS, no framework. Keep it under 300 lines.

### A6: GitHub Action (stretch)
> Read AGENTS.md first. Create `action/action.yml` (a composite action) that scans a preview URL on each PR, comments the score and top 3 fixes, and fails if the score drops more than a threshold versus the last scan. Document usage in README.
