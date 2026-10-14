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
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from core.llm import LLM, Completion
from core.rag.retrieve import RetrievedChunk, Retriever

PROMPT = """You are a senior web performance engineer.
A Lighthouse audit of {url} reported this problem:

Audit: {audit_id}
Title: {title}
Details: {description}
Estimated savings: {savings}

{sources_block}
Give ONE concrete fix a developer could apply today. Respond as JSON with keys:
"diagnosis" (1-2 sentences on the root cause),
"fix" (the specific change to make),
"code" (a short snippet: HTML/CSS/JS/config showing the change, or "" if none),
"sources_used" (list of source numbers you relied on, [] if none).
"""


@dataclass
class FindingInput:
    url: str
    audit_id: str
    title: str
    description: str = ""
    savings_ms: float | None = None


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


def _sources_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines = ["Use these reference sources (cite by number):"]
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] ({c.source}) {c.text[:1200]}")
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
