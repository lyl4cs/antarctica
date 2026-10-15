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


class OffenderOut(BaseModel):
    """One resource behind a finding (from Lighthouse's details), worst first."""

    url: str
    wasted_kb: float | None = None
    wasted_ms: float | None = None
    total_kb: float | None = None


class PlatformOut(BaseModel):
    """What the site is built on, detected from evidence (see core/fixes/context.py)."""

    id: str
    name: str
    evidence: list[str] = []


class StoredFinding(BaseModel):
    id: int
    audit_id: str
    title: str
    description: str
    score: float | None
    savings_ms: float | None
    savings_bytes: float | None
    offenders: list[OffenderOut] = []


class ConditionsOut(BaseModel):
    """What the score was measured under. See services/scanner/parse.py:Conditions.

    Shown next to the score, and used to refuse a before/after comparison between
    two scans that weren't measured the same way. Every field is optional: scans
    recorded before this existed report unknown rather than disappearing.
    """

    lighthouse_version: str | None = None
    form_factor: str | None = None
    throttling_method: str | None = None
    cpu_slowdown: float | None = None
    rtt_ms: float | None = None
    throughput_kbps: float | None = None
    benchmark_index: float | None = None


class Report(BaseModel):
    scan: Scan
    performance_score: int | None
    metrics: dict[str, float | None]
    findings: list[StoredFinding]
    platform: PlatformOut | None = None
    conditions: ConditionsOut = ConditionsOut()


class ScanSummary(BaseModel):
    """One row of a site's scan history: used for before/after comparisons."""

    scan: Scan
    performance_score: int | None


class Stats(BaseModel):
    """Public usage numbers (GET /stats). Counts only, never URLs (ADR 017)."""

    total_scans: int
    completed_scans: int
    unique_sites: int
    scans_last_7_days: int

