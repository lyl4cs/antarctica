"""Antarctica API: submit scans, read results, get AI fix suggestions.

Flow: POST /scans -> row in DB (status=queued) -> job published to Pub/Sub ->
returns 202 immediately. The scanner service does the slow work asynchronously.

CORS: the React frontend (frontend/, hosted on Vercel) lives on a different origin
than this API, so browsers block its requests unless we answer with
Access-Control-Allow-Origin. CORSMiddleware does that for the origins listed in
CORS_ORIGINS only, never "*". See docs/DECISIONS.md, ADR 014.
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl

from core.fixes.context import Offender, detect_platform, extract_offenders
from core.fixes.suggest import FindingInput, suggest_fix
from core.llm import LLM
from core.rag.retrieve import Retriever
from services.common.config import get_settings
from services.common.models import OffenderOut, PlatformOut, Report, Scan, ScanSummary
from services.common.queue import InMemoryPublisher, Publisher, PubSubPublisher
from services.common.store import InMemoryStore, PostgresStore, Store

app = FastAPI(title="Antarctica")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


@lru_cache
def get_store() -> Store:
    s = get_settings()
    return PostgresStore(s.database_url) if s.database_url else InMemoryStore()


@lru_cache
def get_publisher() -> Publisher:
    s = get_settings()
    return PubSubPublisher(s.project_id, s.scan_topic) if s.project_id else InMemoryPublisher()


class ScanRequest(BaseModel):
    url: HttpUrl


INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return INDEX_HTML


# Not /healthz: Cloud Run's Google Front End reserves that path and never forwards it.
@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/scans", status_code=202)
def create_scan(
    req: ScanRequest,
    store: Store = Depends(get_store),
    publisher: Publisher = Depends(get_publisher),
) -> Scan:
    scan = store.create_scan(str(req.url))
    publisher.publish({"scan_id": scan.id, "url": scan.url})
    return scan


@app.get("/scans")
def recent_scans(limit: int = 20, store: Store = Depends(get_store)) -> list[ScanSummary]:
    """Newest scans across every URL (the home page's "Recent scans").

    No route clash with GET /scans/{scan_id}: that path needs a second segment,
    so "/scans" and "/scans/<id>" can never match the same request."""
    return store.list_recent(limit=max(1, min(limit, 100)))


@app.get("/sites/scans")
def site_history(url: HttpUrl, limit: int = 20, store: Store = Depends(get_store)) -> list[ScanSummary]:
    """Past scans for one URL, newest first. Normalizes the URL the same way POST /scans does,
    so 'https://a.com' and 'https://a.com/' match."""
    return store.list_scans(str(url), limit=max(1, min(limit, 100)))


@app.get("/scans/{scan_id}")
def get_scan(scan_id: str, store: Store = Depends(get_store)) -> Scan:
    scan = store.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


@app.get("/scans/{scan_id}/report")
def get_report(scan_id: str, store: Store = Depends(get_store)) -> Report:
    scan = store.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    report = store.get_report(scan_id)
    if not report:
        raise HTTPException(status_code=409, detail=f"scan is {scan.status}, no report yet")
    return add_evidence(report, store)


def add_evidence(report: Report, store: Store) -> Report:
    """Attach the platform and each finding's offending resources, computed from the
    stored raw Lighthouse JSON (works for scans made before v2 too). If the raw data
    is missing, the report is returned unchanged rather than failing."""
    ev = store.get_evidence(report.scan.id, [f.audit_id for f in report.findings])
    if not ev:
        return report
    platform = detect_platform(ev)
    findings = [
        f.model_copy(update={"offenders": [OffenderOut(**asdict(o))
                                           for o in extract_offenders(ev, f.audit_id)]})
        for f in report.findings
    ]
    return report.model_copy(update={
        "findings": findings,
        "platform": PlatformOut(id=platform.id, name=platform.name, evidence=platform.evidence),
    })


@lru_cache
def get_ai() -> tuple[LLM, Retriever] | None:  # pragma: no cover - needs GCP
    s = get_settings()
    if not (s.project_id and s.database_url):
        return None
    from core.llm import VertexEmbedder, VertexLLM
    from core.rag.retrieve import PgVectorStore

    llm = VertexLLM(s.project_id, s.region, s.llm_model)
    retriever = Retriever(VertexEmbedder(s.project_id, s.region, s.embed_model),
                          PgVectorStore(s.database_url))
    return llm, retriever


class FixOut(BaseModel):
    audit_id: str
    title: str
    diagnosis: str
    fix: str
    code: str
    sources: list[str]
    latency_ms: float
    cost_usd: float
    # site URLs in the fix whose folder the audit never saw: shown as a warning
    unverified_urls: list[str] = []


@app.get("/scans/{scan_id}/fixes")
def get_fixes(
    scan_id: str,
    limit: int = 3,
    rag: bool = True,
    store: Store = Depends(get_store),
    ai: tuple[LLM, Retriever] | None = Depends(get_ai),
) -> list[FixOut]:
    """AI fix suggestions for the top-N findings (biggest estimated savings first)."""
    if ai is None:
        raise HTTPException(status_code=503, detail="AI not configured (PROJECT_ID/DATABASE_URL)")
    report = get_report(scan_id, store)
    llm, retriever = ai
    # Rebuild the full Platform (with prompt guidance) from the same evidence.
    ev = store.get_evidence(scan_id, [f.audit_id for f in report.findings])
    platform = detect_platform(ev) if ev else None
    out: list[FixOut] = []
    for f in report.findings[: max(1, min(limit, 10))]:
        s = suggest_fix(
            FindingInput(
                report.scan.url, f.audit_id, f.title, f.description, f.savings_ms,
                offenders=[Offender(**o.model_dump()) for o in f.offenders],
                platform=platform,
            ),
            llm, retriever, use_rag=rag,
        )
        out.append(FixOut(
            audit_id=f.audit_id, title=f.title, diagnosis=s.diagnosis, fix=s.fix, code=s.code,
            sources=s.cited_sources(), unverified_urls=s.unverified_urls,
            latency_ms=s.completion.latency_ms, cost_usd=s.completion.cost_usd,
        ))
    return out
