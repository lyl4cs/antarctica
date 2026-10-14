# Evals

`cases.jsonl` = real findings + the fix you've verified is correct (`reference_fix`).
See `cases.example.jsonl` for the format. Aim for 30+ cases across 8+ audit types.

Run: `python -m core.evals.run_eval core/evals/cases.jsonl` → prints a summary and saves
`core/evals/results/<timestamp>.json`.

Reported metrics: accepted-fix rate (with vs. without RAG), p95 latency, mean latency,
tokens/sec, cost per request. Read the docstring in `run_eval.py` for the honesty rules.
