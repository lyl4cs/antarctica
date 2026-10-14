from fastapi.testclient import TestClient

from services.api.main import app

client = TestClient(app)


def test_create_and_get_scan():
    res = client.post("/scans", json={"url": "https://example.com"})
    assert res.status_code == 202
    scan = res.json()
    assert scan["status"] == "queued"
    got = client.get(f"/scans/{scan['id']}")
    assert got.status_code == 200
    assert got.json()["url"].startswith("https://example.com")


def test_bad_url_rejected():
    assert client.post("/scans", json={"url": "not a url"}).status_code == 422


def test_unknown_scan_404():
    assert client.get("/scans/nope").status_code == 404
