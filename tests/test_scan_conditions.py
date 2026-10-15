"""Measurement conditions: parsed, stored, and served next to the score.

A Lighthouse score is only meaningful relative to the device, throttling and
engine version it was measured under (ADR 022). These tests cover capturing that,
and surviving reports that don't carry it.
"""

from fastapi.testclient import TestClient

from services.api import main
from services.common.queue import InMemoryPublisher
from services.common.store import InMemoryStore
from services.scanner.parse import parse_conditions, parse_report


def test_parses_the_default_mobile_profile(lhr):
    c = parse_conditions(lhr)
    assert c.lighthouse_version == "12.2.1"
    assert c.form_factor == "mobile"
    assert c.throttling_method == "simulate"
    assert c.cpu_slowdown == 4
    assert c.rtt_ms == 150
    assert c.throughput_kbps == 1638.4


def test_captures_host_speed_separately_from_the_site(lhr):
    """benchmark_index describes the machine, not the page. It's why an unchanged
    site can move a few points between runs."""
    assert parse_conditions(lhr).benchmark_index == 1250.5


def test_a_report_without_config_still_parses(lhr):
    """Hand-supplied or older reports shouldn't blow up, just report unknown."""
    bare = {k: v for k, v in lhr.items() if k not in ("configSettings", "environment")}
    c = parse_conditions(bare)
    assert c.form_factor is None and c.cpu_slowdown is None and c.benchmark_index is None
    assert c.lighthouse_version == "12.2.1"  # still at the top level


def test_desktop_unthrottled_is_a_different_profile(lhr):
    desktop = {**lhr, "configSettings": {
        "formFactor": "desktop", "throttlingMethod": "provided",
        "throttling": {"cpuSlowdownMultiplier": 1},
    }}
    a, b = parse_conditions(lhr), parse_conditions(desktop)
    assert (a.form_factor, a.cpu_slowdown) != (b.form_factor, b.cpu_slowdown)


def test_parse_report_carries_conditions(lhr):
    assert parse_report(lhr).conditions.form_factor == "mobile"


def test_report_endpoint_serves_conditions(scan_result):
    store = InMemoryStore()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_publisher] = lambda: InMemoryPublisher()
    try:
        client = TestClient(main.app)
        scan_id = client.post("/scans", json={"url": "https://a.com"}).json()["id"]
        store.save_result(scan_id, scan_result.report, scan_result.raw, 1.0)
        c = client.get(f"/scans/{scan_id}/report").json()["conditions"]
        assert c["form_factor"] == "mobile"
        assert c["lighthouse_version"] == "12.2.1"
        assert c["cpu_slowdown"] == 4
        assert c["benchmark_index"] == 1250.5
    finally:
        main.app.dependency_overrides.clear()


def test_conditions_default_to_unknown_not_missing(scan_result):
    """An old scan with no conditions must still return the key, so the UI can say
    'unknown' instead of crashing on an absent field."""
    store = InMemoryStore()
    scan_result.report.conditions = type(scan_result.report.conditions)()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_publisher] = lambda: InMemoryPublisher()
    try:
        client = TestClient(main.app)
        scan_id = client.post("/scans", json={"url": "https://a.com"}).json()["id"]
        store.save_result(scan_id, scan_result.report, scan_result.raw, 1.0)
        c = client.get(f"/scans/{scan_id}/report").json()["conditions"]
        assert set(c) >= {"form_factor", "lighthouse_version", "benchmark_index"}
        assert all(v is None for v in c.values())
    finally:
        main.app.dependency_overrides.clear()
