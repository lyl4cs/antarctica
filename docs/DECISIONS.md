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
