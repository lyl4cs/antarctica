"""Review drafted reference fixes one at a time and promote the ones you agree with.

    python -m scripts.review_cases core/evals/cases.draft.jsonl

WHY THIS IS A SEPARATE STEP
`build_cases` writes a `reference_draft` for every finding. A draft is a guess from
a table (see core/evals/references.py); the eval's answer key has to be a person's
judgement. This walks the drafts, shows you the finding, the draft and the doc page
to check it against, and writes `reference_fix` only when you say so. Nothing is
promoted in bulk and there is no "accept all": waving thirty drafts through would
produce an eval that measures nothing, and would be invisible in the result file.

Keys: [y] accept, [e] edit (type your own), [s] skip for now, [q] save and quit.

Output is written in place, so the run is resumable: stop after ten, come back, and
only the still-unreviewed cases come up again. When every case you intend to use is
reviewed, copy the reviewed ones out:

    python -m scripts.review_cases core/evals/cases.draft.jsonl --export core/evals/cases.jsonl

The export drops drafts and anything still unreviewed, which is the file run_eval
expects. (run_eval refuses a case with an empty reference_fix anyway, so a
half-reviewed file cannot quietly become a reported number.)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.evals.references import doc_for

Case = dict[str, Any]


def load(path: Path) -> list[Case]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(cases: list[Case], path: Path) -> None:
    path.write_text("".join(json.dumps(c) + "\n" for c in cases))


def needs_review(case: Case) -> bool:
    """True while this case has no human-approved reference fix."""
    return not str(case.get("reference_fix", "")).strip()


def promote(case: Case, text: str) -> Case:
    """Accept `text` as this case's reference fix and drop the draft.

    The draft is removed rather than kept alongside, so a later reader cannot
    mistake the machine's wording for the approved one.
    """
    if not text.strip():
        raise ValueError("a reference fix cannot be empty")
    out = {k: v for k, v in case.items() if k != "reference_draft"}
    out["reference_fix"] = text.strip()
    return out


def reviewed(cases: list[Case]) -> list[Case]:
    """Only the cases a person has approved: what the eval is allowed to see."""
    return [{k: v for k, v in c.items() if k != "reference_draft"}
            for c in cases if not needs_review(c)]


def progress(cases: list[Case]) -> tuple[int, int]:
    """(approved, total), for the line printed between cases."""
    return sum(not needs_review(c) for c in cases), len(cases)


def render(case: Case) -> str:
    """What the reviewer reads before deciding. Offenders included: the draft names
    them, so a reviewer has to be able to see whether it named the right ones."""
    offenders = [str(o.get("url", "")) for o in case.get("offenders") or []][:5]
    lines = [
        f"  url        {case.get('url', '')}",
        f"  audit      {case.get('audit_id', '')}",
        f"  title      {case.get('title', '')}",
    ]
    if case.get("savings_ms"):
        lines.append(f"  savings    {case['savings_ms']} ms")
    for i, o in enumerate(offenders):
        lines.append(f"  {'offenders' if i == 0 else '         '}  {o}")
    doc = doc_for(str(case.get("audit_id", "")))
    lines.append(f"\n  draft      {case.get('reference_draft') or '(none: write one yourself)'}")
    lines.append(f"  check it   {doc or '(no doc for this audit)'}")
    return "\n".join(lines)


def main() -> None:  # pragma: no cover - interactive
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--export", help="write the approved cases to this file and stop")
    a = ap.parse_args()
    path = Path(a.path)
    cases = load(path)

    if a.export:
        keep = reviewed(cases)
        Path(a.export).write_text("".join(json.dumps(c) + "\n" for c in keep))
        print(f"exported {len(keep)} approved cases -> {a.export} "
              f"({len(cases) - len(keep)} still unreviewed, left behind)")
        return

    for i, case in enumerate(cases):
        if not needs_review(case):
            continue
        done, total = progress(cases)
        print(f"\n[{done}/{total} approved] {case.get('id')}")
        print(render(case))
        while True:
            choice = input("\n  [y]es  [e]dit  [s]kip  [q]uit > ").strip().lower()
            if choice in ("y", "e", "s", "q"):
                break
        if choice == "q":
            break
        if choice == "s":
            continue
        text = case.get("reference_draft") or ""
        if choice == "e" or not text:
            text = input("  reference fix > ").strip()
            if not text:
                continue
        cases[i] = promote(case, text)
        save(cases, path)

    done, total = progress(cases)
    save(cases, path)
    print(f"\nsaved {path}: {done}/{total} approved.")
    if done:
        print(f"export with: python -m scripts.review_cases {path} --export core/evals/cases.jsonl")


if __name__ == "__main__":  # pragma: no cover
    main()
