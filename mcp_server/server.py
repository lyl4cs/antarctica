"""MCP server: lets AI assistants (Claude, Gemini, Cursor...) run Antarctica as tools.

WHAT MCP IS
The Model Context Protocol is a standard plug between an AI assistant and outside
systems. A server advertises tools (name + JSON-schema inputs + description); the
assistant decides when to call them and reads the results. This server exposes
four tools that wrap the deployed Antarctica API:

    run_audit(url)            -> starts a scan, waits for it, returns score + top findings
    get_report(scan_id)       -> full metrics and findings for a finished scan
    suggest_fixes(scan_id, n) -> RAG-grounded Gemini fixes for the top-n findings
    site_history(url)         -> past scores for a URL (before/after over time)

DESIGN CHOICES
- Thin wrapper over the HTTP API, not the database. The assistant gets exactly the
  same behavior and permissions as any other API client; no second code path to keep
  in sync, and no database credentials on the user's laptop.
- Compact results. Tool output goes into the model's context window, so results are
  trimmed (top findings, seconds instead of raw ms) instead of dumping the raw
  Lighthouse JSON. Smaller context = cheaper and more accurate tool use.
- Errors the model can act on. Expected failures (bad URL, scan failed, AI not
  configured) raise ToolError with a plain message, which reaches the model as an
  error result it can explain or recover from. Anything else is a crash and stays
  in the server log.
- Blocking HTTP runs in a worker thread (anyio.to_thread) and polling uses
  anyio.sleep, so the server's event loop never freezes while a scan runs.

Run it (stdio transport, launched by the assistant):
    ANTARCTICA_API_URL=https://<your-api> antarctica-mcp
"""

from __future__ import annotations

import json
import os
import urllib.error
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from scripts.api_client import ApiClient

MAX_FINDINGS = 5


def _sec(ms: float | None) -> float | None:
    return None if ms is None else round(ms / 1000, 2)


def summarize_report(report: dict, max_findings: int = MAX_FINDINGS) -> dict:
    """Shrink an API report to what a model needs: score, metrics in seconds, top findings."""
    m = report["metrics"]
    return {
        "scan_id": report["scan"]["id"],
        "url": report["scan"]["url"],
        "performance_score": report["performance_score"],
        "metrics": {
            "lcp_s": _sec(m.get("lcp_ms")),
            "fcp_s": _sec(m.get("fcp_ms")),
            "tbt_s": _sec(m.get("tbt_ms")),
            "speed_index_s": _sec(m.get("speed_index_ms")),
            "cls": m.get("cls"),
        },
        "top_findings": [
            {
                "audit_id": f["audit_id"],
                "title": f["title"],
                "est_savings_s": _sec(f.get("savings_ms")),
                "est_savings_kb": (None if f.get("savings_bytes") is None
                                   else round(f["savings_bytes"] / 1024)),
                # the files to change, worst first (v2 evidence; 3 keeps context small)
                "worst_resources": [
                    {k: o[k] for k in ("url", "wasted_kb", "wasted_ms") if o.get(k) is not None}
                    for o in (f.get("offenders") or [])[:3]
                ],
            }
            for f in report["findings"][:max_findings]
        ],
        "total_findings": len(report["findings"]),
        "platform": (report.get("platform") or {}).get("name"),
    }


def _api_error(e: urllib.error.HTTPError) -> ToolError:
    try:
        detail = json.loads(e.read() or b"{}").get("detail", e.reason)
    except (ValueError, OSError):
        detail = e.reason
    return ToolError(f"Antarctica API returned {e.code}: {detail}")


class AntarcticaTools:
    """Tool logic, separate from MCP wiring so it can be unit-tested with a fake client."""

    def __init__(self, client: Any, poll_s: float = 5, timeout_s: float = 300,
                 sleep: Callable[[float], Awaitable[None]] = anyio.sleep) -> None:
        self.client, self.poll_s, self.timeout_s, self.sleep = client, poll_s, timeout_s, sleep

    async def _call(self, fn: Callable[..., Any], *args: Any) -> Any:
        try:
            return await anyio.to_thread.run_sync(fn, *args)
        except urllib.error.HTTPError as e:
            raise _api_error(e) from e
        except urllib.error.URLError as e:
            raise ToolError(f"Could not reach the Antarctica API: {e.reason}") from e

    async def run_audit(self, url: str) -> dict:
        if not url.startswith(("http://", "https://")):
            raise ToolError("url must start with http:// or https://")
        scan = await self._call(self.client.create_scan, url)
        waited = 0.0
        while True:
            scan = await self._call(self.client.get_scan, scan["id"])
            if scan["status"] == "failed":
                raise ToolError(f"Scan of {url} failed after {scan['attempts']} attempt(s): "
                                f"{scan.get('error') or 'unknown error'}")
            if scan["status"] == "done":
                break
            if waited >= self.timeout_s:
                raise ToolError(f"Scan {scan['id']} still {scan['status']} after "
                                f"{self.timeout_s:.0f}s; call get_report later with this id.")
            await self.sleep(self.poll_s)
            waited += self.poll_s
        return summarize_report(await self._call(self.client.get_report, scan["id"]))

    async def get_report(self, scan_id: str) -> dict:
        return summarize_report(await self._call(self.client.get_report, scan_id), 20)

    async def suggest_fixes(self, scan_id: str, limit: int = 3) -> list[dict]:
        fixes = await self._call(self.client.fixes, scan_id, max(1, min(limit, 5)))
        return [
            {
                "audit_id": f["audit_id"],
                "title": f["title"],
                "diagnosis": f["diagnosis"],
                "where": f.get("where", ""),
                "fix": f["fix"],
                "code": f["code"],
                "sources": list(dict.fromkeys(f["sources"])),  # dedupe, keep order
                # paths the audit never saw: tell the user to check them
                "unverified_urls": f.get("unverified_urls", []),
            }
            for f in fixes
        ]

    async def site_history(self, url: str) -> list[dict]:
        rows = await self._call(self.client.history, url)
        return [
            {
                "scan_id": r["scan"]["id"],
                "status": r["scan"]["status"],
                "created_at": r["scan"]["created_at"],
                "performance_score": r["performance_score"],
            }
            for r in rows
        ]


def build_server(tools: AntarcticaTools) -> MCPServer:
    server = MCPServer(
        "antarctica",
        instructions=(
            "Antarctica audits website speed with Lighthouse and suggests code fixes "
            "grounded in web.dev docs. Typical flow: run_audit(url) -> read top_findings -> "
            "suggest_fixes(scan_id) for the worst ones. Scores are 0-100 (higher is better); "
            "a single run varies by a few points, so compare several runs before concluding."
        ),
    )

    @server.tool(
        description="Run a Lighthouse performance audit on a URL and wait for it (30-90 s). "
                    "Returns score, core metrics in seconds, and the top findings by savings.",
        annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
    )
    async def run_audit(url: str) -> dict:
        return await tools.run_audit(url)

    @server.tool(
        description="Get the full report (score, metrics, up to 20 findings) for a finished scan.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_report(scan_id: str) -> dict:
        return await tools.get_report(scan_id)

    @server.tool(
        description="AI-suggested fixes (diagnosis, fix, code, sources) for the top `limit` "
                    "findings of a finished scan (1-5). Each fix is one Gemini call (~3-5 s, "
                    "<$0.001), so ask only for what you need.",
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    )
    async def suggest_fixes(scan_id: str, limit: int = 3) -> list[dict]:
        return await tools.suggest_fixes(scan_id, limit)

    @server.tool(
        description="Past scans of a URL, newest first, with scores. Use for before/after.",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def site_history(url: str) -> list[dict]:
        return await tools.site_history(url)

    return server


def main() -> None:  # pragma: no cover - started by the assistant over stdio
    api = os.environ.get("ANTARCTICA_API_URL")
    if not api:
        raise SystemExit("Set ANTARCTICA_API_URL to your deployed API, e.g. https://...run.app")
    build_server(AntarcticaTools(ApiClient(api, timeout=120))).run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
