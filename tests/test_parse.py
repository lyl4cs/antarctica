import json
from pathlib import Path

from services.scanner.parse import parse_report

LHR = json.loads((Path(__file__).parent / "fixtures" / "lhr_small.json").read_text())


def test_metrics_parsed():
    r = parse_report(LHR)
    assert r.url == "https://example.com/"
    assert r.metrics.performance_score == 47
    assert r.metrics.lcp_ms == 5320.2
    assert r.metrics.cls == 0.21


def test_only_failing_opportunities_sorted_by_savings():
    r = parse_report(LHR)
    ids = [f.audit_id for f in r.findings]
    assert ids == ["unused-javascript", "render-blocking-resources"]


def test_missing_fields_dont_crash():
    r = parse_report({"requestedUrl": "https://x.dev", "audits": {}})
    assert r.metrics.performance_score is None
    assert r.findings == []
