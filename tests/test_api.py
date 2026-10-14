import json

import pytest
from fastapi.testclient import TestClient

from core.llm import HashEmbedder, ScriptedLLM
from core.rag.chunk import DocChunk
from core.rag.retrieve import InMemoryVectorStore, Retriever
from services.api import main
from services.common.queue import InMemoryPublisher
from services.common.store import InMemoryStore


@pytest.fixture
def ctx():
    store, pub = InMemoryStore(), InMemoryPublisher()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_publisher] = lambda: pub
    main.app.dependency_overrides[main.get_ai] = lambda: None
    yield TestClient(main.app), store, pub
    main.app.dependency_overrides.clear()


def test_create_scan_queues_job(ctx):
    client, _, pub = ctx
    res = client.post("/scans", json={"url": "https://example.com"})
    assert res.status_code == 202
    scan = res.json()
    assert scan["status"] == "queued"
    assert pub.jobs == [{"scan_id": scan["id"], "url": scan["url"]}]
    assert client.get(f"/scans/{scan['id']}").json()["url"].startswith("https://example.com")


def test_bad_url_and_unknown_scan(ctx):
    client, _, _ = ctx
    assert client.post("/scans", json={"url": "not a url"}).status_code == 422
    assert client.get("/scans/nope").status_code == 404


def test_report_only_after_done(ctx, scan_result):
    client, store, _ = ctx
    scan_id = client.post("/scans", json={"url": "https://example.com"}).json()["id"]
    assert client.get(f"/scans/{scan_id}/report").status_code == 409
    store.save_result(scan_id, scan_result.report, scan_result.raw, scan_result.duration_ms)
    rep = client.get(f"/scans/{scan_id}/report").json()
    assert rep["performance_score"] == 47
    assert rep["findings"][0]["audit_id"] == "unused-javascript"


def test_fixes_503_without_ai(ctx, scan_result):
    client, _, _ = ctx
    scan_id = client.post("/scans", json={"url": "https://example.com"}).json()["id"]
    assert client.get(f"/scans/{scan_id}/fixes").status_code == 503


def test_fixes_with_ai(ctx, scan_result):
    client, store, _ = ctx
    retriever = Retriever(HashEmbedder(), InMemoryVectorStore())
    retriever.ingest([DocChunk("web.dev/js", "Unused JS", "Remove unused JavaScript with code splitting")])
    reply = json.dumps({"diagnosis": "d", "fix": "split bundles", "code": "import()", "sources_used": [1]})
    main.app.dependency_overrides[main.get_ai] = lambda: (ScriptedLLM([reply]), retriever)
    scan_id = client.post("/scans", json={"url": "https://example.com"}).json()["id"]
    store.save_result(scan_id, scan_result.report, scan_result.raw, scan_result.duration_ms)
    fixes = client.get(f"/scans/{scan_id}/fixes?limit=1").json()
    assert fixes[0]["fix"] == "split bundles"
    assert fixes[0]["sources"] == ["web.dev/js"]


def test_site_history_newest_first_with_scores(ctx, scan_result):
    client, store, _ = ctx
    first = client.post("/scans", json={"url": "https://example.com"}).json()["id"]
    store.save_result(first, scan_result.report, scan_result.raw, scan_result.duration_ms)
    second = client.post("/scans", json={"url": "https://example.com/"}).json()["id"]
    client.post("/scans", json={"url": "https://other.com"})
    hist = client.get("/sites/scans", params={"url": "https://example.com"}).json()
    assert [h["scan"]["id"] for h in hist] == [second, first]
    assert hist[0]["performance_score"] is None and hist[1]["performance_score"] == 47


def test_index_page_served(ctx):
    client, _, _ = ctx
    res = client.get("/")
    assert res.status_code == 200 and "Antarctica" in res.text
    assert "innerHTML" not in res.text.split("<script>")[1].replace("never innerHTML", "")
