"""Integration tests: PostgresStore and PgVectorStore against real Postgres + pgvector."""

from __future__ import annotations

import threading
import uuid

from core.llm import HashEmbedder
from core.rag.chunk import chunk_markdown
from core.rag.retrieve import PgVectorStore, Retriever
from infra.migrate import apply_migrations
from services.common.store import PostgresStore


def test_migrations_are_idempotent(db_url):
    assert apply_migrations(db_url) == []  # already applied by the fixture


def test_create_and_get_scan(clean_db):
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    got = store.get_scan(scan.id)
    assert got is not None and got.url == "https://a.com"
    assert got.status == "queued" and got.attempts == 0
    assert store.get_scan(str(uuid.uuid4())) is None


def test_start_attempt_counts_and_marks_running(clean_db):
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    assert store.start_attempt(scan.id) == 1
    assert store.start_attempt(scan.id) == 2
    assert store.get_scan(scan.id).status == "running"


def test_save_result_and_report(clean_db, scan_result):
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    assert store.get_report(scan.id) is None  # not done yet

    assert store.save_result(scan.id, scan_result.report, scan_result.raw, 1234.0) is True
    report = store.get_report(scan.id)
    assert report.scan.status == "done" and report.scan.duration_ms == 1234.0
    assert report.performance_score == 47
    assert report.metrics["lcp_ms"] == 5320.2
    # biggest time savings first
    assert [f.audit_id for f in report.findings] == ["unused-javascript",
                                                     "render-blocking-resources"]


def test_duplicate_delivery_writes_once(clean_db, scan_result):
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    store.save_result(scan.id, scan_result.report, scan_result.raw, 1.0)
    assert store.save_result(scan.id, scan_result.report, scan_result.raw, 1.0) is False
    assert len(store.get_report(scan.id).findings) == 2  # not 4


def test_concurrent_deliveries_only_one_wins(clean_db, scan_result):
    """Two workers get the same Pub/Sub message at once. SELECT ... FOR UPDATE must
    make the second one wait, see status='done', and back off."""
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    results: list[bool] = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.append(store.save_result(scan.id, scan_result.report, scan_result.raw, 1.0))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False, True]
    assert len(store.get_report(scan.id).findings) == 2


def test_mark_failed_truncates_error(clean_db):
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    store.mark_failed(scan.id, "x" * 5000)
    got = store.get_scan(scan.id)
    assert got.status == "failed" and len(got.error) == 2000 and got.finished_at


def test_list_scans_newest_first_with_scores(clean_db, scan_result):
    store = PostgresStore(clean_db)
    first = store.create_scan("https://a.com")
    store.save_result(first.id, scan_result.report, scan_result.raw, 1.0)
    second = store.create_scan("https://a.com")
    store.create_scan("https://other.com")

    history = store.list_scans("https://a.com")
    assert [h.scan.id for h in history] == [second.id, first.id]
    assert [h.performance_score for h in history] == [None, 47]
    assert len(store.list_scans("https://a.com", limit=1)) == 1


def test_list_recent_across_urls_newest_first(clean_db, scan_result):
    store = PostgresStore(clean_db)
    first = store.create_scan("https://a.com")
    store.save_result(first.id, scan_result.report, scan_result.raw, 1.0)
    second = store.create_scan("https://b.com")
    third = store.create_scan("https://a.com")

    recent = store.list_recent()
    assert [r.scan.id for r in recent] == [third.id, second.id, first.id]
    assert [r.performance_score for r in recent] == [None, None, 47]  # LEFT JOIN keeps unscored
    assert [r.scan.id for r in store.list_recent(limit=2)] == [third.id, second.id]


def test_pgvector_retrieval_ranks_relevant_chunk_first(clean_db):
    doc = (
        "# Defer non-critical CSS\nRender blocking stylesheets delay first paint.\n\n"
        "# Lazy load images\nUse loading lazy on offscreen images below the fold.\n"
    )
    with PgVectorStore(clean_db) as vectors:
        retriever = Retriever(HashEmbedder(), vectors)
        assert retriever.ingest(chunk_markdown(doc, "web.dev/test")) == 2
        top = retriever.retrieve("offscreen images lazy", k=2)

    assert "Lazy load images" in top[0].text
    assert top[0].source == "web.dev/test"
    assert top[0].score > top[1].score  # cosine similarity, higher = closer


def test_get_evidence_matches_python_slim_extract(clean_db, scan_result):
    """The SQL in PostgresStore.get_evidence must return exactly what slim_lhr does,
    so platform detection and offenders behave the same in prod and in tests."""
    import copy

    from core.fixes.context import slim_lhr

    raw = copy.deepcopy(scan_result.raw)
    raw["stackPacks"] = [{"id": "wordpress", "title": "WordPress"}]
    raw["audits"]["unused-javascript"]["details"]["items"] = [
        {"url": "https://a.com/v.js", "wastedBytes": 1000, "totalBytes": 2000}]
    raw["audits"]["network-requests"] = {"details": {"items": [{"url": "https://a.com/"}]}}
    store = PostgresStore(clean_db)
    scan = store.create_scan("https://a.com")
    store.save_result(scan.id, scan_result.report, raw, 1.0)

    ids = ["unused-javascript", "render-blocking-resources"]
    assert store.get_evidence(scan.id, ids) == slim_lhr(raw, ids)
    assert store.get_evidence(str(uuid.uuid4()), ids) is None
