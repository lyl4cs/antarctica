"""Evaluate fix suggestions WITH vs WITHOUT RAG. Produces the resume numbers.

HOW IT WORKS
- cases.jsonl: real findings you collected, each with the fix an expert (you,
  checking web.dev) agrees is correct ("reference_fix").
- For each case we generate a suggestion twice: use_rag=False and use_rag=True.
- A judge decides if each suggestion is ACCEPTABLE (would actually fix the issue
  and matches the reference in substance). The judge is an LLM by default.

HONESTY RULES (non-negotiable for resume numbers)
1. Spot-check at least 10 judge verdicts by hand. If you disagree with the judge
   more than ~1 in 10 times, fix the judge prompt or label by hand.
2. Don't tune prompts on the same cases you report. Split: dev cases to iterate,
   held-out cases for the final number.
3. Keep every results file. A number you can't reproduce isn't a number.

Run:  python -m core.evals.run_eval core/evals/cases.jsonl
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.fixes.context import Offender, platform_from_dict
from core.fixes.suggest import FindingInput, FixSuggestion, suggest_fix
from core.llm import LLM
from core.rag.retrieve import Retriever

JUDGE_PROMPT = """You are grading a web performance fix.
Problem: {title}
Reference fix (known correct): {reference}
Proposed fix: {fix}
Proposed code: {code}

Is the proposed fix ACCEPTABLE: would it actually address this problem and agree
in substance with the reference (wording may differ)? Answer JSON:
{{"acceptable": true|false, "reason": "<one sentence>"}}"""


@dataclass
class Case:
    id: str
    url: str
    audit_id: str
    title: str
    description: str
    reference_fix: str
    savings_ms: float | None = None
    # v2 evidence (optional; cases built before v2 simply don't have it). Carried in
    # the case so the eval prompt matches production exactly.
    offenders: list[dict] = field(default_factory=list)
    platform: dict | None = None


@dataclass
class CaseResult:
    case_id: str
    use_rag: bool
    acceptable: bool
    judge_reason: str
    fix: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float


def load_cases(path: Path) -> list[Case]:
    return [Case(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def judge(llm: LLM, case: Case, s: FixSuggestion) -> tuple[bool, str]:
    c = llm.complete(
        JUDGE_PROMPT.format(title=case.title, reference=case.reference_fix, fix=s.fix,
                            code=s.code[:800]),
        json_mode=True,
    )
    try:
        d = json.loads(c.text)
        return bool(d.get("acceptable")), str(d.get("reason", ""))
    except json.JSONDecodeError:
        return False, "judge returned invalid JSON"


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def summarize(results: list[CaseResult]) -> dict:
    out = {}
    for mode in (False, True):
        rs = [r for r in results if r.use_rag == mode]
        if not rs:
            continue
        lat = [r.latency_ms for r in rs]
        out["with_rag" if mode else "without_rag"] = {
            "cases": len(rs),
            "accepted_rate": round(sum(r.acceptable for r in rs) / len(rs), 3),
            "p95_latency_ms": round(p95(lat), 1),
            "mean_latency_ms": round(statistics.mean(lat), 1),
            "tokens_per_sec": round(
                sum(r.tokens_out for r in rs) / (sum(lat) / 1000), 1) if sum(lat) else 0.0,
            "cost_per_request_usd": round(sum(r.cost_usd for r in rs) / len(rs), 6),
        }
    return out


def run(cases: list[Case], llm: LLM, judge_llm: LLM, retriever: Retriever | None,
        k: int = 5) -> tuple[list[CaseResult], dict]:
    results: list[CaseResult] = []
    for case in cases:
        finding = FindingInput(case.url, case.audit_id, case.title, case.description,
                               case.savings_ms,
                               offenders=[Offender(**o) for o in case.offenders],
                               platform=platform_from_dict(case.platform))
        for use_rag in (False, True):
            s = suggest_fix(finding, llm, retriever, use_rag=use_rag, k=k)
            ok, reason = judge(judge_llm, case, s)
            c = s.completion
            results.append(CaseResult(case.id, use_rag, ok, reason, s.fix, c.tokens_in,
                                      c.tokens_out, c.latency_ms, c.cost_usd))
    return results, summarize(results)


def main() -> None:  # pragma: no cover - calls Vertex AI
    from core.llm import VertexEmbedder, VertexLLM
    from core.rag.retrieve import PgVectorStore
    from services.common.config import get_settings

    s = get_settings()
    cases = load_cases(Path(sys.argv[1]))
    llm = VertexLLM(s.project_id, s.region, s.llm_model)
    retriever = Retriever(VertexEmbedder(s.project_id, s.region, s.embed_model),
                          PgVectorStore(s.database_url))
    results, summary = run(cases, llm, llm, retriever)
    out = Path("core/evals/results") / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"summary": summary, "results": [asdict(r) for r in results]},
                              indent=2))
    print(json.dumps(summary, indent=2))
    print(f"saved -> {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
