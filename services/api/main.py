"""Antarctica API: submit scans, read results, get AI fix suggestions.

Flow: POST /scans -> row in DB (status=queued) -> job published to Pub/Sub ->
returns 202 immediately. The scanner service does the slow work asynchronously.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl

from core.fixes.suggest import FindingInput, suggest_fix
from core.llm import LLM
from core.rag.retrieve import Retriever
from services.common.config import get_settings
from services.common.models import Report, Scan, ScanSummary
from services.common.queue import InMemoryPublisher, Publisher, PubSubPublisher
from services.common.store import InMemoryStore, PostgresStore, Store

app = FastAPI(title="Antarctica")


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


@app.get("/healthz")
def healthz() -> dict:
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
    return report


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
    out: list[FixOut] = []
    for f in report.findings[: max(1, min(limit, 10))]:
        s = suggest_fix(
            FindingInput(report.scan.url, f.audit_id, f.title, f.description, f.savings_ms),
            llm, retriever, use_rag=rag,
        )
        out.append(FixOut(
            audit_id=f.audit_id, title=f.title, diagnosis=s.diagnosis, fix=s.fix, code=s.code,
            sources=[c.source for c in s.retrieved],
            latency_ms=s.completion.latency_ms, cost_usd=s.completion.cost_usd,
        ))
    return out
