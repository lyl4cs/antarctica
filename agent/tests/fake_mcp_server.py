"""Our real MCP server, launched over stdio, but backed by a fake API (no network)."""

from mcp_server.server import AntarcticaTools, build_server

REPORT = {
    "scan": {"id": "s1", "url": "https://shop.test/", "status": "done"},
    "performance_score": 71,
    "metrics": {"fcp_ms": 3500.0, "lcp_ms": 5100.0, "tbt_ms": 54.0, "cls": 0.0,
                "speed_index_ms": 5100.0},
    "findings": [
        {"id": 1, "audit_id": "modern-image-formats", "title": "Serve images in next-gen formats",
         "description": "d", "score": 0.0, "savings_ms": 820.0, "savings_bytes": 650000.0},
        {"id": 2, "audit_id": "render-blocking-resources", "title": "Eliminate render-blocking",
         "description": "d", "score": 0.0, "savings_ms": 400.0, "savings_bytes": None},
    ],
}


class FakeApi:
    def create_scan(self, url):
        return {"id": "s1", "url": url, "status": "queued"}

    def get_scan(self, sid):
        return {"id": sid, "status": "done", "attempts": 1}

    def get_report(self, sid):
        return REPORT

    def fixes(self, sid, limit):
        return [{"audit_id": f["audit_id"], "title": f["title"], "diagnosis": "x",
                 "fix": f"fix for {f['audit_id']}", "code": "<img>",
                 "sources": ["https://web.dev/a", "https://web.dev/a"]}
                for f in REPORT["findings"][:limit]]

    def history(self, url):
        return []


async def _no_sleep(_s):
    return None


if __name__ == "__main__":
    build_server(AntarcticaTools(FakeApi(), sleep=_no_sleep)).run("stdio")
