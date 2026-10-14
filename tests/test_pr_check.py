import urllib.error

from scripts.pr_check import MARKER, pr_number_from_event, run_check, verdict


class FakeApi:
    def __init__(self, history, score, ai_ok=True):
        self._history, self.score, self.ai_ok = history, score, ai_ok
        self.created: list[str] = []
        self.history_calls_before_create: int | None = None
        self._history_calls = 0

    def history(self, url):
        self._history_calls += 1
        return self._history

    def create_scan(self, url):
        if self.history_calls_before_create is None:
            self.history_calls_before_create = self._history_calls
        self.created.append(url)
        return {"id": "s1", "url": url, "status": "queued"}

    def get_scan(self, sid):
        return {"id": sid, "status": "done"}

    def get_report(self, sid):
        return {"performance_score": self.score,
                "metrics": {"lcp_ms": 2500.0, "tbt_ms": 150.0, "cls": 0.05},
                "findings": [{"title": f"Finding {i}", "description": f"desc {i}"}
                             for i in range(5)]}

    def fixes(self, sid, limit=3):
        if not self.ai_ok:
            raise urllib.error.HTTPError("u", 503, "AI not configured", {}, None)
        return [{"title": "Defer CSS", "fix": "inline critical css"}]


def done(score, status="done"):
    return {"scan": {"status": status}, "performance_score": score}


def test_verdict_threshold_edges():
    assert verdict(75, 80, 5)[0] is True     # dropped exactly 5: allowed
    assert verdict(74, 80, 5)[0] is False    # dropped 6: fail
    assert verdict(10, None, 5)[0] is True   # no baseline: never fail


def test_baseline_read_before_scanning_and_skips_unfinished():
    api = FakeApi([done(None, "running"), done(82)], score=60)
    ok, body, info = run_check(api, "https://pr-1.preview.app", "https://prod.com", 5,
                               sleep=lambda s: None)
    assert api.history_calls_before_create == 1
    assert info["baseline"] == 82 and not ok
    assert MARKER in body and "dropped 22 points" in body
    assert "inline critical css" in body and "LCP" in body


def test_falls_back_to_findings_when_ai_unavailable():
    api = FakeApi([], score=90, ai_ok=False)
    ok, body, _ = run_check(api, "https://a.com", "https://a.com", 5, sleep=lambda s: None)
    assert ok
    assert "Lighthouse findings" in body
    assert "Finding 2" in body and "Finding 3" not in body  # top 3 only


def test_pr_number_from_event(tmp_path):
    p = tmp_path / "event.json"
    p.write_text('{"pull_request": {"number": 7}}')
    assert pr_number_from_event(str(p)) == 7
    p.write_text('{"ref": "refs/heads/main"}')
    assert pr_number_from_event(str(p)) is None
    assert pr_number_from_event(None) is None
