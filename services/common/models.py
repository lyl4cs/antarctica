from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ScanStatus = Literal["queued", "running", "done", "failed"]


class Scan(BaseModel):
    id: str
    url: str
    status: ScanStatus
    attempts: int = 0
    error: str | None = None
    duration_ms: float | None = None
    created_at: datetime
    finished_at: datetime | None = None


class StoredFinding(BaseModel):
    id: int
    audit_id: str
    title: str
    description: str
    score: float | None
    savings_ms: float | None
    savings_bytes: float | None


class Report(BaseModel):
    scan: Scan
    performance_score: int | None
    metrics: dict[str, float | None]
    findings: list[StoredFinding]


class ScanSummary(BaseModel):
    """One row of a site's scan history: used for before/after comparisons."""

    scan: Scan
    performance_score: int | None
