"""MCP server tests: real MCP client <-> server round trips, in-process, with a fake API."""

import io
import json
import urllib.error

import anyio
import pytest
from mcp import Client

from mcp_server.server import AntarcticaTools, build_server, summarize_report

REPORT = {
    "scan": {"id": "s1", "url": "https://a.com/", "status": "done"},
    "performance_score": 71,
    "metrics": {"fcp_ms": 3529.7, "lcp_ms": 5144.5, "tbt_ms": 54.0, "cls": 0.0,
                "speed_index_ms": 5110.1},
    "findings": [
        {"id": i, "audit_id": f"audit-{i}", "title": f"Finding {i}", "description": "d",
         "score": 0.0, "savings_ms": 1000.0 - i * 100, "savings_bytes": 2048.0}
        for i in range(8)
    ],
}


class FakeApi:
    def __init__(self, statuses=("queued", "running", "done"), fixes_error=None):
        self.statuses = list(statuses)
        self.fixes_error = fixes_error
        self.created: list[str] = []

    def create_scan(self, url):
        self.created.append(url)
        return {"id": "s1", "url": url, "status": "queued"}

    def get_scan(self, sid):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return {"id": sid, "status": status, "attempts": 3, "error": "Navigation timeout"}

    def get_report(self, sid):
        return REPORT

    def fixes(self, sid, limit):
        if self.fixes_error:
            raise self.fixes_error
        return [{"audit_id": "audit-0", "title": "Finding 0", "diagnosis": "x", "fix": "y",
                 "code": "<img loading=lazy>", "sources": ["u1", "u1", "u2"],
                 "latency_ms": 1.0, "cost_usd": 0.0}][:limit]

    def history(self, url):
        return [{"scan": {"id": "s1", "status": "done", "created_at": "t"},
                 "performance_score": 71}]


async def _no_sleep(_s):
    return None


def tools(api):
    return AntarcticaTools(api, poll_s=1, timeout_s=10, sleep=_no_sleep)


def call(api, name, args):
    async def go():
        async with Client(build_server(tools(api))) as c:
            return await c.call_tool(name, args)
    return anyio.run(go)


def payload(result):
    return json.loads(result.content[0].text)


def test_summarize_converts_to_seconds_and_trims():
    s = summarize_report(REPORT)
    assert s["metrics"]["lcp_s"] == 5.14 and s["metrics"]["cls"] == 0.0
    assert len(s["top_findings"]) == 5 and s["total_findings"] == 8
    assert s["top_findings"][0] == {"audit_id": "audit-0", "title": "Finding 0",
                                    "est_savings_s": 1.0, "est_savings_kb": 2,
                                    "worst_resources": []}
    assert s["platform"] is None


def test_summarize_includes_platform_and_worst_resources():
    rep = {**REPORT, "platform": {"id": "wordpress", "name": "WordPress"},
           "findings": [{**REPORT["findings"][0], "offenders": [
               {"url": f"https://a.com/{i}.jpg", "wasted_kb": 100 - i, "wasted_ms": None}
               for i in range(5)]}]}
    s = summarize_report(rep)
    assert s["platform"] == "WordPress"
    assert s["top_findings"][0]["worst_resources"] == [
        {"url": f"https://a.com/{i}.jpg", "wasted_kb": 100 - i} for i in range(3)]


def test_server_lists_four_tools_with_schemas():
    async def go():
        async with Client(build_server(tools(FakeApi()))) as c:
            return (await c.list_tools()).tools
    listed = {t.name: t for t in anyio.run(go)}
    assert set(listed) == {"run_audit", "get_report", "suggest_fixes", "site_history"}
    assert listed["run_audit"].input_schema["required"] == ["url"]


def test_run_audit_polls_until_done():
    api = FakeApi()
    result = call(api, "run_audit", {"url": "https://a.com"})
    assert not result.is_error
    assert payload(result)["performance_score"] == 71
    assert api.created == ["https://a.com"]


def test_run_audit_reports_failed_scan_to_the_model():
    result = call(FakeApi(statuses=["failed"]), "run_audit", {"url": "https://a.com"})
    assert result.is_error
    assert "failed after 3 attempt(s): Navigation timeout" in result.content[0].text


def test_run_audit_rejects_non_http_urls_without_calling_api():
    api = FakeApi()
    result = call(api, "run_audit", {"url": "ftp://a.com"})
    assert result.is_error and api.created == []


def test_suggest_fixes_dedupes_sources():
    result = call(FakeApi(), "suggest_fixes", {"scan_id": "s1", "limit": 1})
    data = json.loads(result.content[0].text)
    fix = data[0] if isinstance(data, list) else data
    assert fix["sources"] == ["u1", "u2"]


def test_api_http_errors_become_readable_tool_errors():
    err = urllib.error.HTTPError("u", 503, "Service Unavailable", {},
                                 io.BytesIO(b'{"detail": "AI not configured"}'))
    result = call(FakeApi(fixes_error=err), "suggest_fixes", {"scan_id": "s1"})
    assert result.is_error
    assert "503: AI not configured" in result.content[0].text


@pytest.mark.parametrize("statuses", [["queued"]])
def test_run_audit_times_out_with_scan_id(statuses):
    result = call(FakeApi(statuses=statuses), "run_audit", {"url": "https://a.com"})
    assert result.is_error and "s1" in result.content[0].text
