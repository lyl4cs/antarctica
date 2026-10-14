"""Antarctica API: submit scans and read results.

TODO (agent task T2): replace the in-memory store with Cloud SQL and publish to Pub/Sub.
The in-memory version exists so tests and local dev work on day one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Antarctica")


class ScanRequest(BaseModel):
    url: HttpUrl


class Scan(BaseModel):
    id: str
    url: str
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime


_SCANS: dict[str, Scan] = {}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/scans", status_code=202)
def create_scan(req: ScanRequest) -> Scan:
    scan = Scan(
        id=str(uuid.uuid4()),
        url=str(req.url),
        status="queued",
        created_at=datetime.now(timezone.utc),
    )
    _SCANS[scan.id] = scan
    # T2: publish {"scan_id": scan.id, "url": scan.url} to Pub/Sub topic "scans"
    return scan


@app.get("/scans/{scan_id}")
def get_scan(scan_id: str) -> Scan:
    if scan_id not in _SCANS:
        raise HTTPException(status_code=404, detail="scan not found")
    return _SCANS[scan_id]
