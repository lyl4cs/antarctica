"""Turn a Lighthouse finding into a concrete code-level fix (the "AG" in RAG).

HOW IT WORKS
1. Build a query from the finding (title + description).
2. If RAG is on: retrieve the top-k doc chunks and paste them into the prompt as
   numbered sources. The model is told to ground its fix in those sources.
3. Ask Gemini for strict JSON: diagnosis, fix, code, sources_used.
4. Return the suggestion plus usage (tokens, latency, cost) for the eval.

`use_rag=False` runs the exact same prompt without sources. That's the baseline
the eval compares against: it's how you prove RAG actually helps, instead of
assuming it.

v2 (see core/fixes/context.py): the prompt also carries EVIDENCE from the audit:
the platform the site is built on (detected, with the evidence shown), the exact
offending resources with their waste, and a one-line guide to what this audit
measures. The model is told to use the real URLs and never invent filenames.
Evidence is identical with and without RAG, so the eval still isolates RAG.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from core.fixes.context import Offender, Platform, audit_guide
from core.llm import LLM, Completion
from core.rag.retrieve import RetrievedChunk, Retriever

PROMPT = """You are a senior web performance engineer.
A Lighthouse audit of {url} reported this problem:

Audit: {audit_id}
Title: {title}
Details: {description}
Estimated savings: {savings}
{guide_block}{platform_block}{offenders_block}
{sources_block}
Give ONE concrete fix a developer could apply today, for THIS audit only.
Rules: use the real resource URLs listed above in your code; never invent
filenames or paths; fit the fix to the detected platform; if the platform is
unknown, give a plain HTML/server fix.
Respond as JSON with keys:
"diagnosis" (1-2 sentences on the root cause, naming the worst resources),
"fix" (the specific change to make),
"code" (a short snippet: HTML/CSS/JS/Liquid/config showing the change, or "" if none),
"sources_used" (list of source numbers you relied on, [] if none).
"""


@dataclass
class FindingInput:
    url: str
    audit_id: str
    title: str
    description: str = ""
    savings_ms: float | None = None
    offenders: list[Offender] = field(default_factory=list)
    platform: Platform | None = None


@dataclass
class FixSuggestion:
    audit_id: str
    diagnosis: str
    fix: str
    code: str
    sources_used: list[int]
    used_rag: bool
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    completion: Completion | None = None

    def cited_sources(self) -> list[str]:
        """Source URLs the model actually cited, deduped in order. Several chunks can
        come from one article, so without dedupe the same link showed up 4 times.
        Falls back to everything retrieved if the model cited nothing."""
        cited = [self.retrieved[i - 1].source for i in self.sources_used
                 if 1 <= i <= len(self.retrieved)]
        return list(dict.fromkeys(cited or [c.source for c in self.retrieved]))


def _sources_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines = ["Use these reference sources (cite by number):"]
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] ({c.source}) {c.text[:1200]}")
    return "\n".join(lines) + "\n"


def _guide_block(audit_id: str) -> str:
    g = audit_guide(audit_id)
    return f"What this audit measures: {g}\n" if g else ""


def _platform_block(p: Platform | None) -> str:
    if p is None:
        return ""
    ev = "; ".join(p.evidence[:3])
    return f"Platform: {p.name} (evidence: {ev}). {p.guidance}\n"


def _offenders_block(offenders: list[Offender]) -> str:
    if not offenders:
        return ""
    lines = ["Offending resources (from the audit, worst first):"]
    for o in offenders:
        parts = []
        if o.wasted_kb is not None:
            parts.append(f"wastes {o.wasted_kb:.0f} KB")
        if o.wasted_ms is not None:
            parts.append(f"{o.wasted_ms} ms")
        if o.total_kb is not None:
            parts.append(f"of {o.total_kb:.0f} KB")
        lines.append(f"- {o.url}" + (f" ({', '.join(parts)})" if parts else ""))
    return "\n".join(lines) + "\n"


def _parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start:end + 1]) if start != -1 and end > start else {}


def suggest_fix(
    finding: FindingInput,
    llm: LLM,
    retriever: Retriever | None = None,
    use_rag: bool = True,
    k: int = 5,
) -> FixSuggestion:
    chunks: list[RetrievedChunk] = []
    if use_rag and retriever is not None:
        chunks = retriever.retrieve(f"{finding.title}. {finding.description}", k=k)
    prompt = PROMPT.format(
        url=finding.url,
        audit_id=finding.audit_id,
        title=finding.title,
        description=finding.description[:1500],
        savings=f"{finding.savings_ms:.0f} ms" if finding.savings_ms else "unknown",
        guide_block=_guide_block(finding.audit_id),
        platform_block=_platform_block(finding.platform),
        offenders_block=_offenders_block(finding.offenders),
        sources_block=_sources_block(chunks),
    )
    completion = llm.complete(prompt, json_mode=True)
    data = _parse(completion.text)
    return FixSuggestion(
        audit_id=finding.audit_id,
        diagnosis=str(data.get("diagnosis", "")),
        fix=str(data.get("fix", "")),
        code=str(data.get("code", "")),
        sources_used=[int(x) for x in data.get("sources_used", []) if str(x).isdigit()],
        used_rag=bool(chunks),
        retrieved=chunks,
        completion=completion,
    )
