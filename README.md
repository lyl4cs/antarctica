# sn0wy

**Paste a URL. Get the files that are slowing your page down, and a fix for each one.**

Lighthouse tells you *"reduce unused JavaScript."* sn0wy tells you *which file*, how many KB of it never runs, and what to change, with the web.dev docs it got that from, and a warning if it made up a path.

**[Try it → www.sn0wy.dev](https://www.sn0wy.dev)** · no sign-up, a scan takes 30–60 seconds

<p align="center">
  <img src="docs/images/home.png" alt="sn0wy home page: a URL field, and an iceberg showing three problems hiding below the waterline" width="820">
</p>

## What you get

A score and the five Core Web Vitals, then every finding ranked by how much time it would actually save:

<p align="center">
  <img src="docs/images/report.png" alt="Report page: performance score 47, LCP/TBT/CLS/FCP/SI tiles, and findings with a Get AI fix button" width="820">
</p>

Hit **Get AI fix** on any finding and Gemini writes a diagnosis, a fix, and a code snippet, grounded in retrieved web-performance docs and in the actual resources your page loaded. So instead of "compress your images" you get the filename, the current size, and the command.

It also tells you what the site is built on (Shopify, Next.js, WordPress, or nothing it recognizes), because the right fix for a Shopify theme is not the right fix for a hand-rolled site.

## The part I'd want you to look at

The first version confidently told me to optimize `https://shopnovus.us/images/model-lifestyle.jpg`. That folder doesn't exist. The image was real, the path was invented, and nothing about the answer looked wrong.

Telling the model not to invent paths helps and does not fix it. So every URL in a generated fix is now checked against the resources Lighthouse actually loaded. Same folder, new filename is fine. `hero.webp` next to the real `hero.jpg` is exactly what a "convert to WebP" fix should say. A folder the audit never saw gets flagged in the UI instead of being handed to you as fact.

[`core/fixes/verify.py`](core/fixes/verify.py) · [`tests/test_fix_verify.py`](tests/test_fix_verify.py)

## What it can't do

- **Pages behind a login.** The scanner runs headless Chrome with no credentials, cookies, or custom headers. If the page needs auth, it can't be scanned. No workaround today.
- **Client-rendered pages are fine**, for what it's worth. It's a real browser, and metrics are measured after the JavaScript runs. SPAs and heavy dynamic content scan correctly. Auth is the real gap, not rendering.
- **One URL per scan.** It's not a crawler.
- **Lab data, not field data.** Lighthouse's default mobile emulation and throttling, not your real users. Run-to-run variance is a few points; compare medians, not single runs.
- **A fix is a suggestion, not a patch.** Nothing is applied or tested for you. The path check tells you a file is real, not that the change is right for your codebase.

## How it works

<p align="center">
  <img src="docs/images/architecture.svg" alt="Browser to API on Cloud Run, which publishes to Pub/Sub, which pushes to the Lighthouse scanner; results in Neon Postgres; fixes from Gemini grounded by pgvector retrieval" width="900">
</p>

A scan is a queued job, not a long HTTP request: `POST /scans` returns immediately, Pub/Sub pushes the job to the scanner, and the browser polls. Failures retry with backoff and land in a dead-letter topic after five attempts. The scanner runs at concurrency 1 because one Chrome per container is all that fits, and `save_result` takes a row lock so a redelivered message can't write a scan twice.

The fix path retrieves the top 5 chunks from an index of web.dev and Chrome documentation (Vertex `text-embedding-005`, 768 dims, HNSW cosine index in pgvector), and shows only the sources the model actually cites.

Why each of these, and what the alternative was: [docs/DECISIONS.md](docs/DECISIONS.md).

## Does the retrieval actually help?

That's a claim, so there's a harness that measures it. `core/evals` runs the same findings with and without RAG and reports accepted-fix rate against hand-written references, p95 latency, tokens/sec, and cost per request. A fix costs about $0.0007 and takes 3–5 seconds.

## Run it locally

No cloud account needed, it falls back to an in-memory store and queue.

```bash
pip install -e ".[dev,ai]"
python -m pytest -q                         # offline tests; DB tests skip
uvicorn services.api.main:app --reload      # http://127.0.0.1:8000
```

With the React app:

```bash
cd frontend && npm ci && npm run dev        # http://localhost:5173
```

Integration tests against real Postgres + pgvector (CI runs these as a separate job and fails if any skip):

```bash
docker compose up -d
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sn0wy_test
python -m pytest tests/integration -q
```

Deploying your own: [docs/SETUP.md](docs/SETUP.md).

## Three other ways to use it

**GitHub Action.** Scans your preview deploy on every PR, comments the score and top 3 fixes (one comment, updated in place), and fails the check if the score drops more than `threshold` points below your production baseline.

```yaml
# .github/workflows/perf.yml in the repo you want checked
on: pull_request
permissions: { pull-requests: write }
jobs:
  perf:
    runs-on: ubuntu-latest
    steps:
      - uses: lyl4cs/sn0wy/action@main
        with:
          api-url: https://<your-sn0wy-api>
          url: https://<preview-url-for-this-pr>
          baseline-url: https://<your-production-site>   # optional, defaults to url
          threshold: 5                                   # optional
```

**MCP server.** `sn0wy-mcp` exposes `run_audit`, `get_report`, `suggest_fixes`, and `site_history` over stdio, so Claude or Cursor can audit a site mid-conversation. Setup: [docs/MCP.md](docs/MCP.md).

**ADK agent.** A Google ADK agent that drives those MCP tools in a ReAct loop and returns a prioritized plan with a per-step trace of latency and tokens. Setup: [agent/README.md](agent/README.md).

## Layout

| | |
|---|---|
| `services/` | API, scanner worker, shared store and queue |
| `core/` | LLM clients, RAG, fix suggester, path verification, evals |
| `frontend/` | React + TypeScript app on Vercel |
| `mcp_server/` · `agent/` | MCP tools and the ADK agent |
| `infra/` · `db/migrations/` | gcloud scripts, numbered SQL |
| `docs/` | [DECISIONS.md](docs/DECISIONS.md) (why), [SETUP.md](docs/SETUP.md) (how), [TASKS.md](docs/TASKS.md) (next) |

## Contributing

The most useful thing you can send costs you no code at all: **a fix that was confidently wrong.** [Open an issue](https://github.com/lyl4cs/sn0wy/issues/new?labels=bad-fix) with the URL you scanned and what it told you. A path the checker should have flagged and didn't is the best possible bug report.

If you want to write code, the setup is three commands and the tests run offline with no cloud account:

```bash
pip install -e ".[dev,ai]"
python -m pytest -q
ruff check .
```

Issues tagged [good first issue](https://github.com/lyl4cs/sn0wy/labels/good%20first%20issue) are scoped small on purpose and name the file to change. Two areas where domain knowledge beats my own:

- **[`PLACEMENT` in `core/fixes/context.py`](core/fixes/context.py)** says which file a fix goes in for each platform. If you know Webflow or Squarespace or Drupal better than I do, that table is wrong in ways I can't see. It's plain text with a unit test, and you don't need to understand the rest of the codebase to fix an entry.
- **[`AUDIT_GUIDES`](core/fixes/context.py)** is one line per Lighthouse audit explaining what it actually measures. Missing audits make fixes vaguer.

Full guide, including how the pieces fit together: [CONTRIBUTING.md](CONTRIBUTING.md).

Built by [Layth Sarama](https://github.com/lyl4cs). Formerly called antarctica.
