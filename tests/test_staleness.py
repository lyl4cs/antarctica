"""A scan whose scanner died must report as failed, not as still running.

The production incident these cover: a scanner image that was OOM-killed on every
delivery left a scan at `attempts: 5, status: running, error: null`. Five is the
Pub/Sub subscription's `--max-delivery-attempts`, not anything the worker chose,
which is the tell: `MAX_SCAN_ATTEMPTS` is 3, so the worker's own `mark_failed`
would have fired on attempt 3 had the process lived long enough to run its
`except` block. It did not, so nothing was ever written, and the row stayed
`running` with no error while the browser polled it every 2 seconds forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.common.models import Scan
from services.common.staleness import (
    DEFAULT_STALE_AFTER_S,
    STALE_ERROR,
    is_stale,
    settle_stale,
)
from services.common.store import InMemoryStore

NOW = datetime(2026, 10, 16, 3, 40, tzinfo=UTC)


def scan(status: str, age_s: float, **kw) -> Scan:
    return Scan(
        id="s1",
        url="https://www.sn0wy.dev/",
        status=status,  # type: ignore[arg-type]
        created_at=NOW - timedelta(seconds=age_s),
        **kw,
    )


# ------------------------------------------------------------------ is_stale --

@pytest.mark.parametrize("status", ["queued", "running"])
def test_pending_scan_past_the_deadline_is_stale(status):
    assert is_stale(scan(status, 901), NOW) is True


@pytest.mark.parametrize("status", ["queued", "running"])
def test_pending_scan_inside_the_deadline_is_not(status):
    assert is_stale(scan(status, 899), NOW) is False


@pytest.mark.parametrize("status", ["done", "failed"])
def test_a_settled_scan_never_goes_stale(status):
    """A finished scan is finished however old it is."""
    assert is_stale(scan(status, 10_000), NOW) is False


def test_the_boundary_is_strictly_past_the_deadline():
    assert is_stale(scan("running", DEFAULT_STALE_AFTER_S), NOW) is False
    assert is_stale(scan("running", DEFAULT_STALE_AFTER_S + 1), NOW) is True


def test_naive_timestamps_do_not_raise():
    """An in-memory fixture may carry a naive datetime; Postgres rows do not."""
    # Intentionally tz-naive: that is the condition under test, hence the suppression.
    naive = Scan(id="s1", url="u", status="running", created_at=datetime(2026, 10, 16, 3, 0))  # noqa: DTZ001
    assert is_stale(naive, NOW) is True


# --------------------------------------------------------------- settle_stale --

def test_settle_reports_failed_with_an_explanation():
    out = settle_stale(scan("running", 901), NOW)
    assert out.status == "failed"
    assert out.error == STALE_ERROR
    assert "never finished" in out.error


def test_settle_reproduces_the_production_row():
    """attempts 5, running, no error: exactly what the dead scanner left behind."""
    stuck = scan("running", 1200, attempts=5, error=None)
    out = settle_stale(stuck, NOW)
    assert out.status == "failed"
    assert out.attempts == 5  # the evidence of what happened is kept
    assert out.error == STALE_ERROR


def test_settle_returns_the_same_object_when_nothing_is_wrong():
    """Called on every row of a history list, so the common path must be free."""
    fresh = scan("running", 5)
    assert settle_stale(fresh, NOW) is fresh


def test_settle_never_writes_to_the_scan_it_was_given():
    stuck = scan("running", 901)
    settle_stale(stuck, NOW)
    assert stuck.status == "running"


def test_a_late_success_still_wins():
    """The property that makes an aggressive deadline safe.

    Staleness is derived at read time, never written. If a delivery finally
    succeeds, save_result sets the row to done and this stops applying, so the
    scan reports as the success it turned out to be.
    """
    recovered = scan("done", 100_000)
    assert settle_stale(recovered, NOW).status == "done"


def test_the_deadline_is_configurable():
    assert settle_stale(scan("running", 60), NOW, after_s=30).status == "failed"
    assert settle_stale(scan("running", 60), NOW, after_s=3600).status == "running"


# ------------------------------------------------------------- store wiring --

def test_get_scan_settles_a_dead_scan(monkeypatch):
    monkeypatch.setenv("SCAN_STALE_AFTER_S", "1")
    store = InMemoryStore()
    created = store.create_scan("https://www.sn0wy.dev/")
    store.start_attempt(created.id)
    # Backdate past the deadline, the way a real row ages.
    store.scans[created.id].created_at = datetime.now(UTC) - timedelta(seconds=30)

    got = store.get_scan(created.id)
    assert got is not None
    assert got.status == "failed"
    assert got.error == STALE_ERROR


def test_history_settles_a_dead_scan(monkeypatch):
    """The scan page is not the only reader: the history list showed it in-flight too."""
    monkeypatch.setenv("SCAN_STALE_AFTER_S", "1")
    store = InMemoryStore()
    created = store.create_scan("https://www.sn0wy.dev/")
    store.start_attempt(created.id)
    store.scans[created.id].created_at = datetime.now(UTC) - timedelta(seconds=30)

    [row] = store.list_scans("https://www.sn0wy.dev/")
    assert row.scan.status == "failed"


def test_a_healthy_scan_is_untouched_through_the_store(monkeypatch):
    monkeypatch.setenv("SCAN_STALE_AFTER_S", "900")
    store = InMemoryStore()
    created = store.create_scan("https://www.sn0wy.dev/")
    store.start_attempt(created.id)

    got = store.get_scan(created.id)
    assert got is not None
    assert got.status == "running"
    assert got.error is None


# ---------------------------------------------------------------- end to end --

def test_api_reports_a_dead_scan_as_failed(monkeypatch):
    """The contract the frontend depends on.

    ScanPage polls /scans/{id} every 2 s for as long as the status is queued or
    running. Reporting `failed` is what stops the poll and shows the error state
    instead of a spinner that never resolves.
    """
    from datetime import timedelta

    from fastapi.testclient import TestClient

    from services.api import main
    from services.common.queue import InMemoryPublisher

    monkeypatch.setenv("SCAN_STALE_AFTER_S", "1")
    store, pub = InMemoryStore(), InMemoryPublisher()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_publisher] = lambda: pub
    main.app.dependency_overrides[main.get_ai] = lambda: None
    try:
        client = TestClient(main.app)
        scan_id = client.post("/scans", json={"url": "https://www.sn0wy.dev/"}).json()["id"]
        store.start_attempt(scan_id)
        store.scans[scan_id].created_at = datetime.now(UTC) - timedelta(seconds=30)

        body = client.get(f"/scans/{scan_id}").json()
        assert body["status"] == "failed"
        assert body["error"] == STALE_ERROR

        # And the report endpoint stops implying one is still on its way.
        res = client.get(f"/scans/{scan_id}/report")
        assert res.status_code == 409
        assert "failed" in res.json()["detail"]
    finally:
        main.app.dependency_overrides.clear()
