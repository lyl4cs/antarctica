"""Tiny HTTP client for the Antarctica API (stdlib only, so scripts need no extra deps)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 30) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _req(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def create_scan(self, url: str) -> dict:
        return self._req("POST", "/scans", {"url": url})

    def get_scan(self, scan_id: str) -> dict:
        return self._req("GET", f"/scans/{scan_id}")

    def get_report(self, scan_id: str) -> dict:
        return self._req("GET", f"/scans/{scan_id}/report")

    def history(self, url: str) -> list[dict]:
        return self._req("GET", "/sites/scans?" + urllib.parse.urlencode({"url": url}))
