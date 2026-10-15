# Decision log (ADRs)

Each entry: the decision, why, what we gave up. Add one every time you pick between real options.
This file is your interview prep: "why did you choose X?" gets answered here.

---

## 001: Queue between the API and the scanner (Pub/Sub)
**Decision:** The API never runs Lighthouse itself. It publishes a job, and a separate worker runs it.
**Why:** A Lighthouse scan takes 10–60s. If the API ran it inline, requests would time out, and a traffic spike would take the API down. With a queue in between, the API answers instantly (202 Accepted), workers scale on their own, and a failed scan retries without the user doing anything.
**Gave up:** Simplicity. Results arrive asynchronously, so clients have to poll.
**Practice:** *Put slow or unreliable work behind a queue.*

## 002: Dead-letter topic (`scans-dlq`)
**Decision:** After 5 failed deliveries, a message moves to a separate topic.
**Why:** A "poison message" (say, a URL that always crashes Chrome) would otherwise retry forever and block other work. The DLQ isolates it so you can inspect it later.
**Practice:** *Every retry needs a ceiling and somewhere for failures to go.*

## 003: Ack only after the DB commit
**Decision:** The worker acknowledges a Pub/Sub message only after results are saved.
**Why:** If the worker crashes mid-scan, the message gets redelivered, so no work is lost. The flip side is that a message can arrive twice, so writes must be **idempotent** (safe to run twice), which is the same idea as Parallax's duplicate-order protection.
**Practice:** *At-least-once delivery + idempotent writes = reliable.*

## 004: Postgres + pgvector instead of a separate vector database
**Decision:** Store embeddings in the same Postgres as everything else.
**Why:** One database to run, pay for, and back up. You can join vectors with normal data in one query (for example, "similar past findings *for this site*"). At our scale (thousands of chunks), pgvector with an HNSW index is plenty fast.
**Gave up:** At millions of vectors, a dedicated store (Vertex AI Vector Search) would scale better. Know this tradeoff for interviews.

## 005: SQL migrations, never edited after merge
**Decision:** Schema changes are numbered files (`001_`, `002_`, …), each applied once.
**Why:** Every machine and environment (desktop, laptop, Cloud SQL) ends up with the identical schema by replaying the files in order. Editing an old migration means machines that already ran it silently drift.

## 006: Parse Lighthouse output into our own model
**Decision:** `parse_report()` turns huge raw Lighthouse JSON into a small `ParsedReport` (and we still keep the raw JSON in `audits.raw`).
**Why:** The rest of the system depends on our shape, not Lighthouse's. If Lighthouse changes its format, you fix one function. Keeping the raw copy means you can re-parse old scans later.
**Practice:** *Wrap external data at the boundary.*

## 007: AI-written code, human-owned understanding
**Decision:** Agents (and Claude) may write any part of the code, but every module opens with a docstring explaining how it works and why, and the owner reads and can explain all of it.
**Why:** Shipping speed matters, and so does being able to defend every line in an interview. (Originally the owner was going to write the AI core by hand; that changed to get the MVP shipped faster.)

## 008: Credentials never in the repo; agents never deploy
**Why:** A leaked key or a looping agent can cost real money. The $20 budget alert is the last line of defense, not the first.

## 009: Neon instead of Cloud SQL
**Decision:** Postgres lives on Neon (serverless Postgres with pgvector), not Cloud SQL.
**Why:** Cloud SQL bills ~24/7 even when idle; Neon scales to zero and has a free tier. Same Postgres, same SQL, same pgvector, so switching later is just a connection string.
**Gave up:** Private networking inside GCP. The DB is reached over TLS on the public internet, with credentials kept in Secret Manager.

## 010: Pub/Sub PUSH (not pull) to Cloud Run
**Decision:** Pub/Sub POSTs each job to the scanner's `/pubsub/push`.
**Why:** Cloud Run scales on HTTP requests, so with push the scanner scales to zero when idle and up when jobs arrive. A pull worker would need an always-on instance.
**How ack works:** 2xx = ack, anything else = retry with backoff. After 5 deliveries the message goes to the DLQ. `concurrency=1` because Lighthouse results get noisy when two runs share a CPU.

## 011: Dropped the multi-agent (ADK) design
**Decision:** One well-grounded LLM call per finding, not a planner/diagnoser/fixer agent loop.
**Why:** Reviewers called the original "over-engineered", and the eval is what proves quality. A single call is cheaper, faster, and easier to evaluate. Add agents only if the eval shows a single call failing in ways an agent loop would fix.

## 012: LLM-as-judge, with human spot-checks
**Decision:** The eval uses an LLM to grade fixes against a human-written reference fix.
**Why:** Grading 60+ outputs by hand every run doesn't scale.
**Risk:** Judges can be wrong or biased. Mitigation: spot-check 10+ verdicts per run by hand, and report the number only if agreement is high.

## 013: PR check compares against a baseline URL, fails open on AI
**Decision:** The GitHub Action compares the preview's score against the newest finished scan of `baseline-url` (usually production), and falls back to plain Lighthouse findings if the AI endpoint errors.
**Why:** Preview deploys get a fresh URL per PR, so "last scan of this URL" usually doesn't exist; production is the real comparison. And a perf gate shouldn't go red because Gemini had a bad minute: only the *score* can fail the check.
**Tradeoff:** Lighthouse is noisy (±3–5 points run to run), so the default threshold is 5. A single-run gate will occasionally flake; raising the threshold or scanning 3× and taking the median (like `scripts/measure.py`) are the fixes if it does.

## 014: React + Vite SPA on Vercel, polling for scan status
**Decision:** The UI is a separate single-page app (`frontend/`: React, TypeScript, Vite) deployed on Vercel. It talks to the Cloud Run API over HTTPS with CORS (origins from `CORS_ORIGINS`), and it tracks a running scan by polling `GET /scans/{id}` every 2 seconds.
**Why a separate app instead of FastAPI serving the files:** The API container stays a pure JSON service: no Node build inside the Python image, and a UI change doesn't redeploy (or cold-start) the API. Vercel serves static files from a CDN for free with preview URLs per PR, which also gives the A6 GitHub Action real preview deploys to scan. Cloud Run would bill request time for every JS file.
**Why polling:** A scan changes state about three times in 30–60 s. Polling is ~30 small GETs, works through any proxy, and keeps the API stateless. WebSockets/SSE would hold a connection per viewer on Cloud Run (billed per request-second, with timeouts) for three updates. Revisit if updates become frequent or many people watch the same scan.
**Gave up:** A second deploy target and CORS to configure (`FRONTEND_ORIGIN` in `deploy.sh`), and status shows up to 2 s late.
**Practice:** *Keep the API boring: JSON in, JSON out. Let the CDN serve the UI.*

## 015: MCP server wraps the HTTP API over stdio
**Decision:** The MCP server is a thin client of the public API (not the database), launched by the assistant over stdio.
**Why:** One code path for every client (web UI, GitHub Action, MCP), no database credentials on laptops, and stdio needs no port or auth for local use. Tool results are trimmed (seconds, top findings, deduped sources) because tool output spends the model's context.
**Tradeoff:** `run_audit` blocks for up to ~90 s while the scan runs. Fine for an assistant conversation; a remote multi-user deployment would switch to streamable HTTP with auth and return the scan id immediately instead.
**Known gap:** the API itself is unauthenticated, so anyone with the URL can trigger scans and paid fix calls. Acceptable for a portfolio project with a budget alert; the fix is an API key or IAP in front of Cloud Run.

## 016: ADK agent consumes the MCP server; lives in its own environment
**Decision:** The Gemini agent (Google ADK) gets its tools by launching our MCP server through ADK's `McpToolset`, and it is a separate package in `agent/`.
**Why:** One tool layer for every AI client (Claude Desktop and the Gemini agent use the same four tools), so a fix to a tool fixes it everywhere. `google-adk` 2.12 pins `opentelemetry<=1.42.1` while the Pub/Sub client needs `>=1.44`; a separate environment avoids an unsolvable dependency conflict instead of downgrading production libraries.
**Single agent, not multi-agent:** One LlmAgent with a ReAct loop and a self-check step in the instruction. ADR 011 still holds: add sub-agents only if traces show one agent failing at a step a specialist would fix.
**Tracing:** ADK before/after callbacks record every model and tool call with latency (perf_counter, ms) and token counts, so cost and slowness are attributable to a step.

## 017: Recent scans are per-browser, not global
**Decision:** The home page shows "Your recent scans": ids this browser started, kept in localStorage and looked up one by one. The global `GET /scans` listing is removed. A curated "Example reports" section (`frontend/src/examples.ts`) shows real results to first-time visitors.
**Why:** The global list showed every visitor every URL anyone had scanned (staging sites, private pages), a privacy leak, and it made demos depend on whatever strangers had scanned.
**Tradeoffs:** No history across devices without accounts (deliberately out of scope). Per-URL history (`GET /sites/scans?url=`) stays public, like PageSpeed Insights, since you must already know the URL. Report links stay shareable because scan ids are random UUIDs. Migration 002's index is now unused but stays: applied migrations are never edited.

## 018: Fix prompts carry audit evidence (v2)
**Decision:** Every fix prompt now includes (1) the exact offending resources from Lighthouse's audit details with their waste, (2) the platform detected from evidence (Lighthouse stack packs + URL fingerprints in network requests), and (3) a one-line guide to what the audit measures.
**Why:** v1 fixes were generic (`flower.jpg`), assumed a stack, repeated the same answer for different image audits, and listed one source four times. The evidence was already in the stored raw JSON; we just weren't using it.
**Detection, not assumption:** a site that loads `cdn.shopify.com` assets is labelled "Custom site + Shopify assets", not a Shopify store, because the right fix differs (resize via CDN URL params vs Liquid `image_url`). Unknown stacks get plain HTML/server fixes.
**Computed on read:** evidence is derived from `audits.raw` when a report is requested, so existing scans benefit without re-scanning. Postgres extracts only the needed JSON slices in SQL (`get_evidence`) instead of shipping the whole report (~500 KB) to the API; an integration test pins it to the Python `slim_lhr` output.
**Eval impact (rule 6):** the eval methodology is unchanged (same judge, same with/without-RAG comparison, same metrics). The system under test changed: v2 prompts. Evidence is identical in both arms, so the delta still isolates RAG. Cases now carry `offenders`/`platform` (built by `scripts/build_cases.py`) so eval prompts match production. Build the eval set AFTER deploying v2.
**Sources:** fix responses list the sources the model actually cited, deduped, instead of every retrieved chunk.

