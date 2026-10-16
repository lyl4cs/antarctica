"""Turn real scan findings into a DRAFT eval set.

    python -m scripts.build_cases --api https://<your-api> s1 s2 s3
    python -m scripts.build_cases --api https://<your-api> -      # ids on stdin

The second form reads one scan id per line, so a list pasted out of the database
goes straight in instead of onto a command line:

    SELECT id FROM scans WHERE status = 'done' ORDER BY created_at DESC;

Each line gets everything except `reference_fix`, which is left EMPTY on purpose:
that answer key has to be a person's judgement, and a machine-written one would
make the eval measure a model agreeing with itself. What each line DOES get is a
`reference_draft` (see core/evals/references.py): the canonical remedy for that
audit, naming the files this scan actually blamed, for you to accept, rewrite or
reject in scripts/review_cases.py. Only that review writes `reference_fix`, and
run_eval refuses a case without one.

Dedupes by (url, audit_id) so one site with five identical findings doesn't
dominate the score.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.evals.references import draft_reference
from scripts.api_client import ApiClient


def build_cases(client: ApiClient, scan_ids: list[str], out: Path) -> int:
    seen: set[tuple[str, str]] = set()
    rows = []
    for sid in scan_ids:
        report = client.get_report(sid)
        url = report["scan"]["url"]
        for f in report["findings"]:
            key = (url, f["audit_id"])
            if key in seen:
                continue
            seen.add(key)
            offenders = f.get("offenders", [])
            rows.append({
                "id": f"case-{len(rows) + 1:03d}",
                "url": url,
                "audit_id": f["audit_id"],
                "title": f["title"],
                "description": f.get("description", ""),
                "savings_ms": f.get("savings_ms"),
                # v2 evidence, so the eval prompt matches production exactly
                "offenders": offenders,
                "platform": report.get("platform"),
                "reference_fix": "",
                "reference_draft": draft_reference(f["audit_id"], offenders),
            })
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return len(rows)


def read_ids(args: list[str], stdin_text: str) -> list[str]:
    """Scan ids from the command line, or from stdin when the only argument is "-"."""
    if args == ["-"]:
        return [line.strip() for line in stdin_text.splitlines() if line.strip()]
    return args


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("scan_ids", nargs="+", help='scan ids, or "-" to read them from stdin')
    ap.add_argument("--api", required=True)
    ap.add_argument("--out", default="core/evals/cases.draft.jsonl")
    a = ap.parse_args()
    ids = read_ids(a.scan_ids, sys.stdin.read() if a.scan_ids == ["-"] else "")
    n = build_cases(ApiClient(a.api), ids, Path(a.out))
    print(f"wrote {n} draft cases to {a.out} from {len(ids)} scans.\n"
          f"Next: python -m scripts.review_cases {a.out}")


if __name__ == "__main__":
    main()
