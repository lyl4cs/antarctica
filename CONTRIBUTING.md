# Contributing

Thanks for looking. This is a solo project, so PRs get read the same day.

## The highest-value contribution isn't code

sn0wy generates fixes with an LLM. When it's wrong, it's wrong confidently, and I only
find out if someone tells me. [Open an issue](https://github.com/lyl4cs/sn0wy/issues/new?labels=bad-fix)
with:

- the URL you scanned
- which finding you asked for a fix on
- what it told you, and what's actually true

The best version of this is a fix that named a file path the site doesn't have, because
there's a checker ([`core/fixes/verify.py`](core/fixes/verify.py)) whose entire job is to
catch that. A path it missed is a bug in the checker, not just a bad answer.

## Setup

No cloud account needed. The API falls back to an in-memory store and queue, and the
tests use fake LLM and embedder implementations, so nothing touches the network.

```bash
pip install -e ".[dev,ai]"
python -m pytest -q        # offline tests; the Postgres ones skip
ruff check .
```

To run the whole thing locally:

```bash
uvicorn services.api.main:app --reload    # terminal 1, http://127.0.0.1:8000
cd frontend && npm ci && npm run dev      # terminal 2, http://localhost:5173
```

Tests that need real Postgres and pgvector:

```bash
docker compose up -d
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sn0wy_test
python -m pytest tests/integration -q
```

## Where things are

| Path | What lives there |
|---|---|
| `services/api/` | FastAPI: scans, reports, fixes, rate limiting |
| `services/scanner/` | Lighthouse runner and the Pub/Sub push worker |
| `services/common/` | Config, pydantic models, the Postgres and in-memory stores |
| `core/rag/` | Chunking, embedding, pgvector retrieval |
| `core/fixes/` | The fix prompt, platform detection, placement, path verification |
| `core/evals/` | With-RAG vs without-RAG measurement |
| `frontend/` | React + TypeScript, Vite, plain CSS |

[docs/DECISIONS.md](docs/DECISIONS.md) explains why each piece is the way it is, including
the options that got rejected. Read the relevant ADR before changing something structural.

## Good places to start

**Platform placement.** [`PLACEMENT` in `core/fixes/context.py`](core/fixes/context.py) maps
a platform and an audit category to the file you'd actually edit. I've used Shopify,
WordPress and Next.js, so those entries are reasonable. Webflow, Squarespace, Wix, Drupal,
Magento and Nuxt are educated guesses. If you work in one of those daily, you will spot
something wrong immediately. It's plain strings with a unit test, and you don't need to
understand the rest of the codebase to fix one.

**Audit guides.** [`AUDIT_GUIDES`](core/fixes/context.py) is one line per Lighthouse audit
describing what it actually measures, which stops the model answering
"efficiently encode images" with a WebP conversion. Lighthouse has more audits than are
covered here.

**Path verification.** [`core/fixes/verify.py`](core/fixes/verify.py) pulls URLs out of
generated text and checks them against the resources the audit really loaded. It currently
handles absolute URLs and quoted root-relative paths. It does not handle
`srcset`, CSS `url()`, or import maps, so a bad path in one of those slips through.

## House rules

These come from [AGENTS.md](AGENTS.md), which is the same set of rules I hold myself to.

- **One thing per PR.** Say what changed, why, and how you tested it.
- **New behavior gets a test.** Data transforms always get a unit test.
- **Tests never hit the network or GCP.** Use the fakes in `core/llm.py`, `InMemoryStore`
  and `InMemoryPublisher`.
- **`ruff check .` and `python -m pytest -q` pass before the PR.** CI runs both, plus the
  Postgres integration job and the frontend tests.
- **Type hints everywhere**, pydantic models at API boundaries.
- **Schema changes get a new numbered migration** in `db/migrations/`. Never edit one
  that's already been applied.
- **New modules open with a short docstring** explaining how the thing works and why it's
  built that way. The existing files show the style. This is a codebase people read to
  learn from, so the comments matter as much as the code.
- **Never commit secrets.** Config comes from environment variables.
- **Changes to `core/evals/`** or to what the reported metrics mean have to be called out
  explicitly in the PR description. Those numbers get quoted, so they can't move quietly.

If something's ambiguous, open a draft PR with the question rather than guessing.
