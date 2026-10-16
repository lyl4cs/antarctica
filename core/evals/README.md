# Evals

`cases.jsonl` = real findings + the fix you've verified is correct (`reference_fix`).
See `cases.example.jsonl` for the format. Aim for 30+ cases across 8+ audit types.

Run: `python -m core.evals.run_eval core/evals/cases.jsonl` → prints a summary and saves
`core/evals/results/<timestamp>.json`.

Reported metrics: accepted-fix rate (with vs. without RAG), p95 latency, mean latency,
tokens/sec, cost per request. Read the docstring in `run_eval.py` for the honesty rules.

## Building the set

Three steps. The middle one is the only one that needs your judgement, and it is the
one the number depends on.

```bash
# 1. real findings out of real scans (ids one per line, e.g. pasted from the database:
#    SELECT id FROM scans WHERE status = 'done' ORDER BY created_at DESC;)
python -m scripts.build_cases --api https://<your-api> - < ids.txt

# 2. review every drafted answer key, one at a time, against the doc it cites
python -m scripts.review_cases core/evals/cases.draft.jsonl

# 3. export the ones you approved
python -m scripts.review_cases core/evals/cases.draft.jsonl --export core/evals/cases.jsonl
```

Step 1 writes a `reference_draft` per case (`references.py`): the canonical remedy for
that audit, naming the files that scan actually blamed. A draft is **not** an answer
key. Step 2 shows you the finding, the draft and the doc page, and writes
`reference_fix` only on an explicit keystroke; there is no accept-all. `run_eval`
refuses any case whose `reference_fix` is empty, so an unreviewed draft cannot become
a reported number by being forgotten.

Then split what you have: iterate on one half, report only the other. A prompt tuned
on the cases it is scored against is not measuring anything.
