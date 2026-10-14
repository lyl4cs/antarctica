"""Scanner worker: pull scan jobs from Pub/Sub, run Lighthouse, store results.

TODO (agent task T3): implement `store_result` and the Pub/Sub pull loop.
Contract:
- Message body: {"scan_id": "<uuid>", "url": "https://..."}
- On success: update scans.status='done', insert into audits and findings.
- On failure: increment scans.attempts. After 3 failures, set status='failed'
  (Pub/Sub dead-letter topic `scans-dlq` catches poison messages).
- Ack only after the DB write commits.
"""

from __future__ import annotations

import json
import os

from services.scanner.run_lighthouse import ScanResult, run_scan

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SUBSCRIPTION = os.environ.get("SCAN_SUBSCRIPTION", "scans-worker")


def handle_message(data: bytes) -> ScanResult:
    job = json.loads(data)
    return run_scan(job["url"])


def store_result(scan_id: str, result: ScanResult) -> None:  # pragma: no cover
    raise NotImplementedError("agent task T3")


def main() -> None:  # pragma: no cover
    raise NotImplementedError("agent task T3: Pub/Sub streaming pull loop")


if __name__ == "__main__":
    main()
