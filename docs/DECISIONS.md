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

## 019: Verify AI fixes against the audit; one working snippet
**Decision:** Every fix is checked against the evidence: any URL on the site's own hosts whose folder Lighthouse never saw is returned as `unverified_urls` and shown as a warning. The prompt now demands URLs copied exactly, new files in the same folder as the original, and ONE pasteable snippet (no commented-out code). Diagnosis/fix text renders inline code.
**Why:** On the live Novus report the model wrote `/images/model-lifestyle.jpg` and wrapped half its code in an HTML comment. Instructions reduce that; only a check catches it. Same-folder new names (`hero.webp` next to `hero.jpg`) are allowed on purpose, because that is what a format fix proposes.
**Eval:** `unverified_urls` is a free, objective quality signal (rate of fixes with invented paths) to report next to the judge's accepted-fix rate. The judge and its methodology are unchanged.

## 020: Rate limits in Postgres before going public
**Decision:** Fixed-window counters in a `rate_counters` table, one atomic `INSERT ... ON CONFLICT DO UPDATE ... RETURNING count` per check. Per IP: 10 scans/hour, 30 AI fixes/hour (one unit per finding requested). Global: 300 scans/day, 600 AI fixes/day. Over the limit = HTTP 429 with `Retry-After`. All four numbers are env vars (`RL_*`).
**Why:** The API is public and unauthenticated; scans and Gemini calls cost money. Shared once in a Discord, it already got strangers' traffic.
**Why Postgres, not memory or Redis:** Cloud Run runs up to 3 API instances, so in-memory counters would give 3x the limit and reset on cold starts. Redis is another service to run; one upsert on Neon costs a few ms at this traffic.
**Client IP:** the LAST `X-Forwarded-For` entry (Cloud Run appends the real caller; earlier entries are client-supplied and spoofable).
**Tradeoff:** fixed windows allow a burst across a boundary; sliding windows aren't worth it here. IP limits don't stop a distributed attacker; the global cap is the backstop.
**Usage numbers:** `GET /stats` (counts only, never URLs) for scans; Vercel Web Analytics for visitors.


## ADR 021: "Where to put it" is a lookup table, not model output

**Context.** Two rounds of user feedback said the same thing from opposite directions:
one reader asked who the tool is for, pointing out that an expert doesn't need code
suggestions and a beginner can't apply them. The gap both descriptions circle is the
step between "your LCP image is 412 KB" and actually changing something: *which file do
I open?* PageSpeed Insights structurally cannot answer that, because it doesn't know
what the site is built on. We detect that already (ADR 018) and were barely using it.

**Decision.** Every fix now carries a `where` string: the file or screen this change
goes in, for the detected platform. It is produced by `placement(platform_id, audit_id)`
in `core/fixes/context.py`, a hand-written table keyed by platform and audit category,
with per-platform and then global fallbacks so it is never empty.

**Why not ask Gemini for it.** That re-creates exactly the bug ADR 019 exists to catch.
The model would confidently answer `snippets/product-card.liquid` for a theme it has
never seen, and unlike a resource URL there is nothing to check it against: we don't
have the user's repository. A wrong entry in a table is our bug and is fixable for
everyone at once; a wrong path invented per request is unfalsifiable. The string is also
free, deterministic, and unit-testable.

The placement line is still pasted into the prompt, so the model's prose agrees with what
the UI shows, and the prompt now forbids naming any project file not listed there.

**Honesty.** Entries are phrased as what is usually true of that platform, never as a
claim about this specific site. Where a fix is impossible on the platform, the table says
so: on hosted Shopify, compression and TTFB aren't the user's to change, and saying that
is more useful than a server fix they cannot apply.

**Effect on the eval.** This changes the prompt, so absolute fix quality may move. It is
added identically to the RAG and non-RAG arms, so the comparison the eval exists to make
is unaffected. Numbers measured before this change aren't comparable to numbers after it.

**Tradeoff.** The table is only as good as its author. Shopify, WordPress and Next.js
entries come from real use; Webflow, Squarespace, Wix, Drupal and Magento are educated
guesses, and are flagged in CONTRIBUTING.md as the best place for someone with that
domain knowledge to correct it.

## ADR 022: Store and show the conditions a score was measured under

**Context.** A reader asked to see the device/network profile and the Lighthouse
version next to the score, so before/after comparisons would be interpretable. He was
describing a correctness problem, not a display preference. A Lighthouse score only
means something relative to the emulated device, the throttling, and the engine that
weighted the metrics. The default run emulates a mid-range phone on a throttled
connection with the CPU slowed 4x; the same page measured as desktop with no
throttling scores far higher without changing. Major Lighthouse versions reweight the
metrics. We already shipped a history chart and a two-scan diff that presented
differences as facts about the site, with no way for anyone to know whether the two
runs were even measured the same way.

**Decision.** Capture the conditions per scan and surface them in two places.

`parse_conditions` pulls `lighthouseVersion`, `configSettings.formFactor`,
`throttlingMethod`, the throttling numbers, and `environment.benchmarkIndex` out of the
raw report. Migration 004 stores them as columns on `audits`, and `Report.conditions`
serves them. The report header shows a line like "Mobile, slow 4G, 4x CPU slowdown,
Lighthouse 12.8.2". Before a two-scan diff renders, `comparabilityProblems` checks
whether the two runs match, and the UI says they aren't comparable instead of showing a
diff that means nothing.

**Columns, not a jsonb blob.** The metrics beside them are columns, and the history list
reads these per scan; extracting from `audits.raw` on every row would detoast a ~500 KB
document each time. All columns are nullable so scans recorded before this keep working
and report unknown.

**benchmarkIndex, which nobody asked for.** Lighthouse throttles relative to the machine
it runs on, so a slower or busier Cloud Run instance makes the simulated phone slower
too. It is the most likely reason an unchanged site moves a few points between runs, and
without it that looks like a bug in the tool. It is shown as context on the report and
as a note when two compared scans ran on machines far apart in speed. It is deliberately
NOT a comparability check: it varies on nearly every run, so blocking on it would block
almost every comparison.

**Major versions only.** Scoring weights are stable within a Lighthouse major, so 12.2
against 12.8 compares fine and only a major difference is flagged.

**Lighthouse is now pinned exactly** in the scanner Dockerfile, not to `@12`. A floating
version silently shifts every score on the next image rebuild and puts an invisible
break in every site's history. Bumping it is now a deliberate commit.

**Comparability lives in the frontend.** The diff is computed client-side from two
reports, which is the only consumer today, so the rule is in `frontend/src/lib/conditions.ts`
with its own tests rather than duplicated server-side for a caller that doesn't exist.
If the MCP server ever needs it, it moves to Python and the frontend calls it.

**Also: a "?" on every metric.** The same reasoning applies one level down. The target
user knows their site is slow but has not heard of Total Blocking Time, so each metric
carries a plain-English explanation on the report and in the history diff, sourced from
one `help` field on `METRICS` so both read the same text. It is a button, not a `title`
attribute, because `title` never appears on touch and isn't keyboard reachable.
