"""PR performance check: the logic behind the GitHub Action in action/action.yml.

    python -m scripts.pr_check --api $API --url $PREVIEW_URL [--baseline-url $PROD_URL]

WHAT IT DOES
1. Looks up the BASELINE score: the newest finished scan of --baseline-url
   (defaults to --url). Looked up *before* scanning so the new scan can't be its own
   baseline.
2. Scans the preview URL and waits for it (reuses scripts.measure.wait_for).
3. Gets the top 3 AI fixes. If AI isn't configured (API returns 503) or errors,
   it falls back to the top 3 Lighthouse findings, so the check never fails
   just because Gemini is down.
4. Writes a markdown comment and posts or updates it on the PR (one comment per PR,
   found by a hidden marker, so re-runs edit it instead of spamming).
5. Exits 1 if the score dropped more than --threshold points below the baseline.

WHY A BASELINE URL
Preview deploys usually get a new URL per PR, so "the last scan of this URL" often
doesn't exist. Comparing against production (--baseline-url) answers the real
question: "does this PR make the site slower than what's live?"

Stdlib only, so the Action needs no `pip install`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from scripts.api_client import ApiClient
from scripts.measure import wait_for

MARKER = "<!-- antarctica-pr-check -->"


def baseline_score(client, url: str) -> int | None:
    for row in client.history(url):  # newest first
        if row["scan"]["status"] == "done" and row["performance_score"] is not None:
            return row["performance_score"]
    return None


def top_fixes(client, scan_id: str, report: dict, n: int = 3) -> tuple[list[dict], bool]:
    """Returns (items, from_ai). Falls back to raw findings if the AI endpoint fails."""
    try:
        return client.fixes(scan_id, limit=n)[:n], True
    except (urllib.error.URLError, OSError, ValueError):
        return [{"title": f["title"], "fix": f.get("description", "")}
                for f in report["findings"][:n]], False


def verdict(score: int, baseline: int | None, threshold: int) -> tuple[bool, str]:
    if baseline is None:
        return True, "No baseline yet: this scan becomes the baseline."
    delta = score - baseline
    if delta < -threshold:
        return False, f"Score dropped {-delta} points (limit {threshold})."
    return True, f"Within limit ({delta:+d} vs baseline, limit -{threshold})."


def render(url: str, score: int, baseline: int | None, ok: bool, why: str,
           metrics: dict, fixes: list[dict], from_ai: bool) -> str:
    def ms(key: str) -> str:
        v = metrics.get(key)
        return "n/a" if v is None else f"{v / 1000:.2f}s"

    cls = metrics.get("cls")
    base = "n/a" if baseline is None else str(baseline)
    lines = [
        MARKER,
        f"### {'✅' if ok else '❌'} Antarctica performance check",
        f"**{url}**: score **{score}** (baseline {base}). {why}",
        "",
        "| LCP | TBT | CLS |",
        "|---|---|---|",
        f"| {ms('lcp_ms')} | {ms('tbt_ms')} | {'n/a' if cls is None else f'{cls:.3f}'} |",
        "",
        f"**Top fixes** ({'AI, grounded in web.dev docs' if from_ai else 'Lighthouse findings'}):",
    ]
    for i, f in enumerate(fixes, 1):
        lines.append(f"{i}. **{f['title']}**: {f.get('fix', '').strip()[:300]}")
    if not fixes:
        lines.append("_No findings._")
    return "\n".join(lines) + "\n"


def run_check(client, url: str, baseline_url: str, threshold: int,
              timeout_s: float = 600, poll_s: float = 10,
              sleep: Callable[[float], None] = time.sleep) -> tuple[bool, str, dict]:
    baseline = baseline_score(client, baseline_url)
    scan = client.create_scan(url)
    final = wait_for(client, scan["id"], timeout_s, poll_s, sleep)
    if final["status"] != "done":
        raise RuntimeError(f"scan failed: {final.get('error')}")
    report = client.get_report(scan["id"])
    score = report["performance_score"]
    ok, why = verdict(score, baseline, threshold)
    fixes, from_ai = top_fixes(client, scan["id"], report)
    body = render(url, score, baseline, ok, why, report["metrics"], fixes, from_ai)
    return ok, body, {"score": score, "baseline": baseline, "scan_id": scan["id"]}


def _gh(method: str, url: str, token: str, body: dict | None = None):
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body else None,
        headers={"authorization": f"Bearer {token}",
                 "accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def upsert_comment(body: str, token: str, repo: str, pr: int,
                   api: str = "https://api.github.com") -> None:  # pragma: no cover
    comments = _gh("GET", f"{api}/repos/{repo}/issues/{pr}/comments?per_page=100", token)
    mine = next((c for c in comments if MARKER in (c.get("body") or "")), None)
    if mine:
        _gh("PATCH", f"{api}/repos/{repo}/issues/comments/{mine['id']}", token, {"body": body})
    else:
        _gh("POST", f"{api}/repos/{repo}/issues/{pr}/comments", token, {"body": body})


def pr_number_from_event(path: str | None) -> int | None:
    if not path or not os.path.exists(path):
        return None
    with open(path) as f:
        event = json.load(f)
    return (event.get("pull_request") or {}).get("number")


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--baseline-url", default="")
    ap.add_argument("--threshold", type=int, default=5)
    a = ap.parse_args()

    ok, body, info = run_check(ApiClient(a.api), a.url, a.baseline_url or a.url, a.threshold)
    print(body)

    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as f:
            f.write(f"score={info['score']}\nbaseline={info['baseline'] or ''}\n"
                    f"passed={str(ok).lower()}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as f:
            f.write(body)

    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    pr = pr_number_from_event(os.environ.get("GITHUB_EVENT_PATH"))
    if token and repo and pr:
        try:
            upsert_comment(body, token, repo, pr)
        except urllib.error.HTTPError as e:  # e.g. forked PR with a read-only token
            print(f"could not comment on PR: {e}", file=sys.stderr)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
