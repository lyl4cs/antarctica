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


class Conditions(BaseModel):
    """The settings a score was measured under, and how fast the machine was.

    A Lighthouse score is meaningless on its own: the same page scores far higher
    as "desktop, no throttling" than as the default throttled mobile phone, and
    major Lighthouse versions reweight the metrics. Two scans are only comparable
    if these match, so we store them per scan and show them next to the score.

    `benchmark_index` is Lighthouse's measure of how fast the HOST machine was.
    Throttling is relative to that host, so a busy or slower Cloud Run instance
    makes the simulated phone slower too. It is why an unchanged site can move a
    few points between runs, and without it that looks like a bug in the tool.
    """

    lighthouse_version: str | None = None
    form_factor: str | None = None            # "mobile" | "desktop"
    throttling_method: str | None = None      # "simulate" | "devtools" | "provided"
    cpu_slowdown: float | None = None         # multiplier, e.g. 4
    rtt_ms: float | None = None               # simulated round-trip time
    throughput_kbps: float | None = None      # simulated download throughput
    benchmark_index: float | None = None      # host speed, NOT a property of the site


class ParsedReport(BaseModel):
    url: str
    lighthouse_version: str | None
    conditions: Conditions = Conditions()
    metrics: Metrics
    findings: list[Finding]


def parse_conditions(lhr: dict) -> Conditions:
    """Measurement settings out of a Lighthouse result. Missing keys stay None:
    an older or hand-supplied report should still parse."""
    cfg = lhr.get("configSettings") or {}
    throttling = cfg.get("throttling") or {}
    env = lhr.get("environment") or {}
    return Conditions(
        lighthouse_version=lhr.get("lighthouseVersion"),
        form_factor=cfg.get("formFactor"),
        throttling_method=cfg.get("throttlingMethod"),
        cpu_slowdown=throttling.get("cpuSlowdownMultiplier"),
        rtt_ms=throttling.get("rttMs"),
        throughput_kbps=throttling.get("throughputKbps"),
        benchmark_index=env.get("benchmarkIndex"),
    )


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
        conditions=parse_conditions(lhr),
        metrics=metrics,
        findings=findings,
    )
