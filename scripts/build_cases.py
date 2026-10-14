"""Turn real scan findings into a DRAFT eval set.

    python -m scripts.build_cases --api https://<your-api> s1 s2 s3 > /dev/null
    # writes core/evals/cases.draft.jsonl

Each line gets everything except `reference_fix`, which is left EMPTY on purpose:
you fill it in yourself from the docs (web.dev / Chrome docs). That human-written
answer key is what makes the eval meaningful. Cases with an empty reference_fix
should be removed before running the eval.

Dedupes by (url, audit_id) so one site with five identical findings doesn't
dominate the score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
            rows.append({
                "id": f"case-{len(rows) + 1:03d}",
                "url": url,
                "audit_id": f["audit_id"],
                "title": f["title"],
                "description": f.get("description", ""),
                "savings_ms": f.get("savings_ms"),
                "reference_fix": "",
            })
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return len(rows)


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("scan_ids", nargs="+")
    ap.add_argument("--api", required=True)
    ap.add_argument("--out", default="core/evals/cases.draft.jsonl")
    a = ap.parse_args()
    n = build_cases(ApiClient(a.api), a.scan_ids, Path(a.out))
    print(f"wrote {n} draft cases to {a.out}. Now fill in every reference_fix by hand.")


if __name__ == "__main__":
    main()
