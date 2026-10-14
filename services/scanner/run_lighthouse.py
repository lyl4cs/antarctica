"""Run the Lighthouse CLI against a URL and return the parsed report."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass

from services.scanner.parse import ParsedReport, parse_report

LIGHTHOUSE_CMD = [
    "lighthouse",
    "--output=json",
    "--output-path=stdout",
    "--only-categories=performance",
    "--quiet",
    "--chrome-flags=--headless=new --no-sandbox --disable-gpu",
]


@dataclass
class ScanResult:
    report: ParsedReport
    raw: dict
    duration_ms: float


class LighthouseError(RuntimeError):
    pass


def run_scan(url: str, timeout_s: int = 120) -> ScanResult:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https://, got {url!r}")
    start = time.perf_counter()
    proc = subprocess.run(
        [*LIGHTHOUSE_CMD, url], capture_output=True, text=True, timeout=timeout_s, check=False
    )
    duration_ms = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        raise LighthouseError(proc.stderr[-2000:])
    raw = json.loads(proc.stdout)
    return ScanResult(report=parse_report(raw), raw=raw, duration_ms=duration_ms)


if __name__ == "__main__":
    import sys

    result = run_scan(sys.argv[1])
    print(result.report.model_dump_json(indent=2))
    print(f"scan took {result.duration_ms:.0f} ms")
