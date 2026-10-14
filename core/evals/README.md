# Evals (OWNER ONLY)

These produce the red numbers on the resume, so they have to be real.

## Eval set
`core/evals/cases.jsonl`: one line per case:
```json
{"id": "case-001", "url": "https://...", "audit_id": "render-blocking-resources", "accepted_fix": "Defer non-critical CSS via media=print onload swap", "notes": "..."}
```
Target: **30+ cases** from real scans (Orland Park, Novus, and a few public sites).

## Metrics to report
| Metric | How |
|---|---|
| Accepted-fix rate | Share of proposals a judge (you, or an LLM judge you've spot-checked) marks as matching `accepted_fix`. Run it **with RAG and without RAG**. The difference is the resume bullet. |
| tokens/sec | tokens_out / generation time |
| p95 latency | Per audit, end to end |
| Cost per audit | Sum of token costs at current Vertex pricing |
| Lighthouse before/after | Only on sites where a fix was actually deployed |

Write each run's results to `core/evals/results/<date>.json` so the numbers can be traced.
