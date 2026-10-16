"""v2 fix evidence: offenders, platform detection, audit guides, prompt, API wiring."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from core.fixes.context import (
    audit_guide,
    detect_platform,
    extract_offenders,
    slim_lhr,
)
from core.fixes.suggest import FindingInput, FixSuggestion, suggest_fix
from core.llm import HashEmbedder, ScriptedLLM
from core.rag.chunk import DocChunk
from core.rag.retrieve import InMemoryVectorStore, RetrievedChunk, Retriever
from services.api import main
from services.common.queue import InMemoryPublisher
from services.common.store import InMemoryStore
from services.scanner.parse import parse_report

SITE = "https://shop.test"


def _requests(*urls):
    return {"details": {"type": "table", "items": [{"url": u, "resourceType": "Other"}
                                                   for u in urls]}}


@pytest.fixture
def lhr_ev(lhr) -> dict:
    """lhr_small plus the parts real Lighthouse 12 reports carry: per-finding items,
    every network request, and stack packs (none here: a hand-built site)."""
    d = copy.deepcopy(lhr)
    a = d["audits"]
    a["unused-javascript"]["details"]["items"] = [
        {"url": f"{SITE}/js/vendor.js", "totalBytes": 400_000, "wastedBytes": 300_000},
        {"url": f"{SITE}/js/app.js", "totalBytes": 120_000, "wastedBytes": 60_000},
        {"url": "data:application/javascript;base64,AAAA", "wastedBytes": 999_999},
    ]
    a["render-blocking-resources"]["details"]["items"] = [
        {"url": f"{SITE}/css/main.css", "totalBytes": 90_000, "wastedMs": 820},
    ]
    a["network-requests"] = _requests(
        f"{SITE}/", f"{SITE}/js/vendor.js",
        "https://cdn.shopify.com/s/files/1/0001/products/serum.jpg?v=1",
    )
    return d


# ---------------------------------------------------------------- offenders --

def test_offenders_worst_first_skip_data_uris(lhr_ev):
    offs = extract_offenders(lhr_ev, "unused-javascript")
    assert [o.url for o in offs] == [f"{SITE}/js/vendor.js", f"{SITE}/js/app.js"]
    assert offs[0].wasted_kb == 293.0 and offs[0].total_kb == 390.6


def test_offenders_ms_only_and_missing_audit(lhr_ev):
    [o] = extract_offenders(lhr_ev, "render-blocking-resources")
    assert o.wasted_ms == 820 and o.wasted_kb is None
    assert extract_offenders(lhr_ev, "no-such-audit") == []


def test_offenders_capped_and_source_url():
    lhr = {"audits": {"x": {"details": {"items": [
        {"source": {"url": f"https://a.test/{i}.js"}, "wastedBytes": i * 1024}
        for i in range(10)]}}}}
    offs = extract_offenders(lhr, "x", n=3)
    assert [o.url for o in offs] == [f"https://a.test/{i}.js" for i in (9, 8, 7)]


# ----------------------------------------------------------------- platform --

def test_shopify_assets_on_custom_site_is_integration_not_store(lhr_ev):
    p = detect_platform(lhr_ev)
    assert p.id == "shopify-integration"
    assert "cdn.shopify.com" in p.evidence[0]
    assert "?width=" in p.guidance


def test_hosted_shopify_theme():
    lhr = {"audits": {"network-requests": _requests(
        "https://store.test/cdn/shop/files/hero.jpg", "https://cdn.shopify.com/x.js")}}
    p = detect_platform(lhr)
    assert p.id == "shopify" and "Liquid" in p.guidance


def test_stack_pack_wins_and_others_listed():
    lhr = {"stackPacks": [{"id": "wordpress", "title": "WordPress"},
                          {"id": "react", "title": "React"}],
           "audits": {"network-requests": _requests("https://b.test/wp-content/x.css")}}
    p = detect_platform(lhr)
    assert p.id == "wordpress"
    assert p.evidence[0] == "Lighthouse detected WordPress"
    assert any("wp-content" in e for e in p.evidence)
    assert p.evidence[-1] == "also detected: React"


def test_nextjs_from_urls_and_custom_fallback():
    nxt = {"audits": {"network-requests": _requests("https://n.test/_next/static/a.js")}}
    assert detect_platform(nxt).id == "nextjs"
    plain = {"audits": {"network-requests": _requests("https://p.test/style.css")}}
    p = detect_platform(plain)
    assert p.id == "custom" and "plain HTML" in p.guidance
    assert detect_platform({}).id == "custom"


def test_slim_extract_gives_same_answers(lhr_ev):
    slim = slim_lhr(lhr_ev, ["unused-javascript"])
    assert set(slim["audits"]) == {"unused-javascript", "network-requests"}
    assert detect_platform(slim).id == detect_platform(lhr_ev).id
    assert extract_offenders(slim, "unused-javascript") == \
        extract_offenders(lhr_ev, "unused-javascript")


def test_audit_guides_keep_image_audits_apart():
    assert "FORMAT" in audit_guide("modern-image-formats")
    assert "COMPRESSION" in audit_guide("uses-optimized-images")
    assert "not a format" in audit_guide("uses-optimized-images").lower()
    assert audit_guide("unknown-audit") == ""


# ------------------------------------------------------------------- prompt --

def _reply(**kw):
    return json.dumps({"diagnosis": "d", "fix": "f", "code": "", "sources_used": [], **kw})


def test_prompt_carries_evidence(lhr_ev):
    llm = ScriptedLLM([_reply()])
    finding = FindingInput(SITE, "unused-javascript", "Reduce unused JavaScript", "d", 900,
                           offenders=extract_offenders(lhr_ev, "unused-javascript"),
                           platform=detect_platform(lhr_ev))
    suggest_fix(finding, llm, None, use_rag=False)
    p = llm.prompts[0]
    assert f"- {SITE}/js/vendor.js (wastes 293 KB, of 391 KB)" in p
    assert "Platform: Custom site + Shopify assets" in p
    assert "What this audit measures: BYTES, not timing" in p
    assert "invent or change a folder" in p


def test_prompt_without_evidence_has_no_empty_sections():
    llm = ScriptedLLM([_reply()])
    suggest_fix(FindingInput(SITE, "x", "t"), llm, None, use_rag=False)
    # The section header itself, not the phrase: the prompt rules now name
    # "Offending resources" when telling the model that block is untrusted data.
    assert "Offending resources (from the audit" not in llm.prompts[0]
    assert "Platform:" not in llm.prompts[0]


def test_cited_sources_deduped_and_fallback():
    chunks = [RetrievedChunk(s, "", "", 1.0) for s in ["u/a", "u/a", "u/b", "u/c"]]
    s = FixSuggestion("x", "", "", "", sources_used=[1, 2, 3, 99], used_rag=True,
                      retrieved=chunks)
    assert s.cited_sources() == ["u/a", "u/b"]  # dupes merged, bogus number ignored
    s.sources_used = []
    assert s.cited_sources() == ["u/a", "u/b", "u/c"]


# ---------------------------------------------------------------------- API --

@pytest.fixture
def api(lhr_ev):
    store = InMemoryStore()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_publisher] = lambda: InMemoryPublisher()
    main.app.dependency_overrides[main.get_ai] = lambda: None
    client = TestClient(main.app)
    scan_id = client.post("/scans", json={"url": SITE}).json()["id"]
    store.save_result(scan_id, parse_report(lhr_ev), lhr_ev, 1.0)
    yield client, scan_id
    main.app.dependency_overrides.clear()


def test_report_includes_platform_and_offenders(api):
    client, scan_id = api
    rep = client.get(f"/scans/{scan_id}/report").json()
    assert rep["platform"]["id"] == "shopify-integration"
    by_id = {f["audit_id"]: f for f in rep["findings"]}
    assert by_id["unused-javascript"]["offenders"][0]["url"] == f"{SITE}/js/vendor.js"
    assert by_id["render-blocking-resources"]["offenders"][0]["wasted_ms"] == 820


def test_fixes_use_evidence_and_cite_deduped_sources(api):
    client, scan_id = api
    retriever = Retriever(HashEmbedder(), InMemoryVectorStore())
    retriever.ingest([DocChunk("web.dev/js", "Unused JS", "Remove unused JavaScript"),
                      DocChunk("web.dev/js", "Split", "Code splitting unused JavaScript")])
    llm = ScriptedLLM([_reply(sources_used=[1, 2])])
    main.app.dependency_overrides[main.get_ai] = lambda: (llm, retriever)
    [fix] = client.get(f"/scans/{scan_id}/fixes?limit=1").json()
    assert fix["sources"] == ["web.dev/js"]
    assert f"{SITE}/js/vendor.js" in llm.prompts[0]
    assert "cdn.shopify.com" in llm.prompts[0]


def test_report_without_raw_still_works():
    store = InMemoryStore()
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_publisher] = lambda: InMemoryPublisher()
    try:
        client = TestClient(main.app)
        scan_id = client.post("/scans", json={"url": SITE}).json()["id"]
        store.save_result(scan_id, parse_report({"audits": {}}), {}, 1.0)
        store.raw.pop(scan_id)  # e.g. a row whose raw JSON is unavailable
        rep = client.get(f"/scans/{scan_id}/report").json()
        assert rep["platform"] is None and rep["findings"] == []
    finally:
        main.app.dependency_overrides.clear()


# --------------------------------------------------------------------- eval --

def test_eval_case_evidence_reaches_the_prompt():
    from core.evals.run_eval import Case, run

    case = Case("c1", SITE, "unused-javascript", "Reduce unused JavaScript", "d",
                "code-split vendor.js", offenders=[{"url": f"{SITE}/js/vendor.js",
                                                    "wasted_kb": 293.0}],
                platform={"id": "nextjs", "name": "Next.js", "evidence": ["requests /_next/"]})
    gen = ScriptedLLM([_reply(), _reply()])
    judge = ScriptedLLM([json.dumps({"acceptable": True, "reason": "ok"})] * 2)
    run([case], gen, judge, None)
    for prompt in gen.prompts:  # same evidence with and without RAG
        assert f"{SITE}/js/vendor.js (wastes 293 KB)" in prompt
        assert "next/image" in prompt  # guidance rebuilt from the platform id


def test_old_cases_without_evidence_still_load(tmp_path):
    from core.evals.run_eval import load_cases

    p = tmp_path / "c.jsonl"
    p.write_text(json.dumps({"id": "c", "url": "u", "audit_id": "a", "title": "t",
                             "description": "d", "reference_fix": "r"}) + "\n")
    [c] = load_cases(p)
    assert c.offenders == [] and c.platform is None


def test_build_cases_copies_evidence(tmp_path):
    from scripts.build_cases import build_cases

    class Api:
        def get_report(self, sid):
            return {"scan": {"url": SITE}, "platform": {"id": "custom", "name": "Custom"},
                    "findings": [{"audit_id": "a", "title": "t", "offenders": [{"url": "x"}]}]}

    out = tmp_path / "draft.jsonl"
    build_cases(Api(), ["s1"], out)
    row = json.loads(out.read_text())
    assert row["offenders"] == [{"url": "x"}] and row["platform"]["id"] == "custom"


def test_fixes_endpoint_returns_unverified_urls(api):
    client, scan_id = api
    reply = _reply(code=f'<script src="{SITE}/static/vendor.js" defer></script>')
    main.app.dependency_overrides[main.get_ai] = lambda: (ScriptedLLM([reply]), None)
    [fix] = client.get(f"/scans/{scan_id}/fixes?limit=1&rag=false").json()
    assert fix["unverified_urls"] == [f"{SITE}/static/vendor.js"]
