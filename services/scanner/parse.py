"""Turn raw Lighthouse JSON into the compact records Antarctica stores."""

from __future__ import annotations

from pydantic import BaseModel

# Lighthouse audit ids -> our metric names
METRIC_AUDITS = {
    "first-contentful-paint": "fcp_ms",
    "largest-contentful-paint": "lcp_ms",
    "total-blocking-time": "tbt_ms",
    "cumulative-layout-shift": "cls",
    "speed-index": "speed_index_ms",
}


class Metrics(BaseModel):
    performance_score: int | None  # 0-100
    fcp_ms: float | None = None
    lcp_ms: float | None = None
    tbt_ms: float | None = None
    cls: float | None = None
    speed_index_ms: float | None = None


class Finding(BaseModel):
    audit_id: str
    title: str
    description: str
    score: float | None
    savings_ms: float | None
    savings_bytes: float | None


class ParsedReport(BaseModel):
    url: str
    lighthouse_version: str | None
    metrics: Metrics
    findings: list[Finding]


def parse_report(lhr: dict) -> ParsedReport:
    """Parse a Lighthouse result (lhr) dict.

    Findings are the failing audits that have estimated savings ("opportunities"),
    sorted by estimated time saved, largest first.
    """
    audits: dict = lhr.get("audits", {})
    perf = lhr.get("categories", {}).get("performance", {}).get("score")

    metric_values = {
        name: audits.get(audit_id, {}).get("numericValue")
        for audit_id, name in METRIC_AUDITS.items()
    }
    metrics = Metrics(
        performance_score=None if perf is None else round(perf * 100),
        **metric_values,
    )

    findings: list[Finding] = []
    for audit_id, audit in audits.items():
        details = audit.get("details") or {}
        if details.get("type") != "opportunity":
            continue
        score = audit.get("score")
        if score is not None and score >= 0.9:  # passing, nothing to fix
            continue
        findings.append(
            Finding(
                audit_id=audit_id,
                title=audit.get("title", audit_id),
                description=audit.get("description", ""),
                score=score,
                savings_ms=details.get("overallSavingsMs"),
                savings_bytes=details.get("overallSavingsBytes"),
            )
        )
    findings.sort(key=lambda f: f.savings_ms or 0, reverse=True)

    return ParsedReport(
        url=lhr.get("finalDisplayedUrl") or lhr.get("finalUrl") or lhr.get("requestedUrl", ""),
        lighthouse_version=lhr.get("lighthouseVersion"),
        metrics=metrics,
        findings=findings,
    )
