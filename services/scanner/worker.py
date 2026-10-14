"""Scanner worker: receives Pub/Sub PUSH messages over HTTP and runs Lighthouse.

HOW RETRIES WORK (interview topic)
Pub/Sub push treats our HTTP status code as the ack:
  - 2xx  -> message acked, done
  - 5xx  -> nack, Pub/Sub redelivers later with backoff
After max delivery attempts (set on the subscription), the message goes to the
dead-letter topic `scans-dlq`.

We also cap attempts ourselves: after MAX_SCAN_ATTEMPTS we mark the scan 'failed'
and return 200 so a permanently broken URL stops burning retries.
Duplicate deliveries are safe because Store.save_result is idempotent.
"""

from __future__ import annotations

import base64
import json
import logging
from functools import lru_cache
from typing import Callable

from fastapi import Depends, FastAPI, Response

from services.common.config import get_settings
from services.common.store import InMemoryStore, PostgresStore, Store
from services.scanner.run_lighthouse import ScanResult, run_scan

log = logging.getLogger("scanner")
app = FastAPI(title="Antarctica scanner")


@lru_cache
def get_store() -> Store:
    s = get_settings()
    return PostgresStore(s.database_url) if s.database_url else InMemoryStore()


def get_scan_fn() -> Callable[[str], ScanResult]:
    return run_scan


def decode_push(body: dict) -> dict:
    """Pub/Sub push wraps our JSON as base64 in body['message']['data']."""
    return json.loads(base64.b64decode(body["message"]["data"]))


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/pubsub/push")
def handle_push(
    body: dict,
    response: Response,
    store: Store = Depends(get_store),
    scan_fn: Callable[[str], ScanResult] = Depends(get_scan_fn),
) -> dict:
    try:
        job = decode_push(body)
        scan_id, url = job["scan_id"], job["url"]
    except (KeyError, ValueError) as e:
        log.error("malformed message: %s", e)
        return {"status": "dropped"}  # 200: a malformed message will never succeed

    scan = store.get_scan(scan_id)
    if scan is None:
        return {"status": "unknown_scan"}
    if scan.status == "done":
        return {"status": "duplicate"}

    attempts = store.start_attempt(scan_id)
    try:
        result = scan_fn(url)
    except Exception as e:  # noqa: BLE001 - any scan failure is retryable
        log.warning("scan %s attempt %s failed: %s", scan_id, attempts, e)
        if attempts >= get_settings().max_scan_attempts:
            store.mark_failed(scan_id, str(e))
            return {"status": "failed"}
        response.status_code = 500  # ask Pub/Sub to retry
        return {"status": "retry"}

    store.save_result(scan_id, result.report, result.raw, result.duration_ms)
    return {"status": "done"}
