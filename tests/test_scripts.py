import json

from scripts.build_cases import build_cases
from scripts.measure import measure


class FakeApi:
    """Simulates the API: each scan is 'running' once, then 'done' with a canned score."""

    def __init__(self, scores, findings=None):
        self.scores = list(scores)
        self.findings = findings or []
        self.scans: dict[str, dict] = {}
        self.polls: dict[str, int] = {}

    def create_scan(self, url):
        sid = f"s{len(self.scans) + 1}"
        self.scans[sid] = {"id": sid, "url": url, "status": "queued",
                           "score": self.scores[len(self.scans)]}
        return self.scans[sid]

    def get_scan(self, sid):
        self.polls[sid] = self.polls.get(sid, 0) + 1
        s = self.scans[sid]
        s["status"] = "done" if self.polls[sid] > 1 else "running"
        return s

    def get_report(self, sid):
        s = self.scans.get(sid) or {"id": sid, "url": "https://a.com", "score": 50}
        return {
            "scan": {"id": sid, "url": s["url"]},
            "performance_score": s["score"],
            "metrics": {"lcp_ms": s["score"] * 10.0, "tbt_ms": 100.0, "cls": 0.1,
                        "fcp_ms": None, "speed_index_ms": None},
            "findings": self.findings,
        }


def test_measure_reports_median_not_mean():
    res = measure(FakeApi([40, 90, 52]), "https://a.com", runs=3, sleep=lambda s: None)
    assert res["runs_ok"] == 3
    assert res["scores"] == [40, 90, 52]
    assert res["performance_score"] == 52  # median ignores the 90 outlier
    assert res["lcp_ms"] == 520.0
    assert res["fcp_ms"] is None


def test_build_cases_dedupes_and_leaves_reference_empty(tmp_path):
    f = {"id": 1, "audit_id": "unused-javascript", "title": "Reduce unused JavaScript",
         "description": "d", "score": 0.3, "savings_ms": 900.0, "savings_bytes": 1.0}
    api = FakeApi([], findings=[f, dict(f, id=2)])
    out = tmp_path / "cases.jsonl"
    n = build_cases(api, ["s1", "s2"], out)
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert n == 1 and len(rows) == 1
    assert rows[0]["audit_id"] == "unused-javascript"
    assert rows[0]["reference_fix"] == ""
