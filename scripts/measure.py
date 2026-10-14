"""Measure a page N times and report MEDIAN metrics, for honest before/after numbers.

    python -m scripts.measure https://shopnovus.us --runs 3 --api https://<your-api>

WHY THE MEDIAN OF SEVERAL RUNS
Lighthouse scores vary run to run (network jitter, server load, CPU contention).
A single "52 -> 81" could be noise. Run 3-5 times before AND after a change and
compare medians: the median ignores one unlucky outlier, unlike the mean.
Record both runs' raw numbers in a notes file so the resume claim is traceable.
"""

from __future__ import annotations

import argparse
import statistics
import time
from typing import Callable

from scripts.api_client import ApiClient

METRICS = ["lcp_ms", "tbt_ms", "cls", "fcp_ms", "speed_index_ms"]


def wait_for(client: ApiClient, scan_id: str, timeout_s: float, poll_s: float,
             sleep: Callable[[float], None]) -> dict:
    waited = 0.0
    while waited <= timeout_s:
        scan = client.get_scan(scan_id)
        if scan["status"] in ("done", "failed"):
            return scan
        sleep(poll_s)
        waited += poll_s
    raise TimeoutError(f"scan {scan_id} not finished after {timeout_s}s")


def measure(client: ApiClient, url: str, runs: int = 3, timeout_s: float = 300,
            poll_s: float = 5, sleep: Callable[[float], None] = time.sleep) -> dict:
    reports = []
    for _ in range(runs):  # sequential on purpose: parallel runs compete for CPU
        scan = client.create_scan(url)
        final = wait_for(client, scan["id"], timeout_s, poll_s, sleep)
        if final["status"] == "done":
            reports.append(client.get_report(scan["id"]))
    if not reports:
        raise RuntimeError("all runs failed")
    out = {
        "url": url,
        "runs_ok": len(reports),
        "performance_score": statistics.median(r["performance_score"] for r in reports),
        "scores": [r["performance_score"] for r in reports],
    }
    for m in METRICS:
        vals = [r["metrics"][m] for r in reports if r["metrics"].get(m) is not None]
        out[m] = round(statistics.median(vals), 3) if vals else None
    return out


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--api", required=True)
    a = ap.parse_args()
    res = measure(ApiClient(a.api), a.url, a.runs)
    for k, v in res.items():
        print(f"{k:>18}: {v}")


if __name__ == "__main__":
    main()
