import base64
import json

import pytest
from fastapi.testclient import TestClient

from services.common.store import InMemoryStore
from services.scanner import worker


def push(job: dict) -> dict:
    return {"message": {"data": base64.b64encode(json.dumps(job).encode()).decode()}}


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setenv("MAX_SCAN_ATTEMPTS", "2")
    store = InMemoryStore()
    worker.app.dependency_overrides[worker.get_store] = lambda: store
    yield TestClient(worker.app), store
    worker.app.dependency_overrides.clear()


def use_scan(fn):
    worker.app.dependency_overrides[worker.get_scan_fn] = lambda: fn


def test_success_saves_and_acks(ctx, scan_result):
    client, store = ctx
    scan = store.create_scan("https://example.com")
    use_scan(lambda url: scan_result)
    res = client.post("/pubsub/push", json=push({"scan_id": scan.id, "url": scan.url}))
    assert res.status_code == 200 and res.json()["status"] == "done"
    assert store.get_scan(scan.id).status == "done"


def test_duplicate_delivery_is_idempotent(ctx, scan_result):
    client, store = ctx
    scan = store.create_scan("https://example.com")
    calls = []
    use_scan(lambda url: calls.append(url) or scan_result)
    body = push({"scan_id": scan.id, "url": scan.url})
    client.post("/pubsub/push", json=body)
    res = client.post("/pubsub/push", json=body)
    assert res.json()["status"] == "duplicate"
    assert len(calls) == 1  # Lighthouse ran once


def test_failure_retries_then_gives_up(ctx):
    client, store = ctx
    scan = store.create_scan("https://broken.example")

    def boom(url):
        raise RuntimeError("chrome crashed")

    use_scan(boom)
    body = push({"scan_id": scan.id, "url": scan.url})
    first = client.post("/pubsub/push", json=body)
    assert first.status_code == 500  # Pub/Sub will redeliver
    second = client.post("/pubsub/push", json=body)
    assert second.status_code == 200 and second.json()["status"] == "failed"
    assert store.get_scan(scan.id).status == "failed"


def test_malformed_message_is_dropped(ctx):
    client, _ = ctx
    res = client.post("/pubsub/push", json={"message": {"data": "bm90IGpzb24="}})
    assert res.status_code == 200 and res.json()["status"] == "dropped"
