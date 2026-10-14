import json

from core.evals.run_eval import Case, p95, run
from core.fixes.suggest import FindingInput, suggest_fix
from core.llm import HashEmbedder, ScriptedLLM
from core.rag.chunk import chunk_markdown
from core.rag.retrieve import InMemoryVectorStore, Retriever

DOC = """# Defer non-critical CSS
Render blocking stylesheets delay first paint. Inline critical CSS and load the rest
asynchronously with rel preload.

# Lazy load images
Use loading lazy on offscreen images below the fold.
"""


def make_retriever() -> Retriever:
    r = Retriever(HashEmbedder(), InMemoryVectorStore())
    r.ingest(chunk_markdown(DOC, "web.dev/test"))
    return r


def test_chunking_splits_on_headings_with_overlap():
    chunks = chunk_markdown(DOC, "src")
    assert [c.heading for c in chunks] == ["Defer non-critical CSS", "Lazy load images"]
    long = chunk_markdown("# H\n" + " ".join(f"w{i}" for i in range(700)), "src", 300, 40)
    assert len(long) == 3
    assert long[0].text.split()[-1] == long[1].text.split()[40]  # overlap carried over


def test_retrieval_ranks_relevant_chunk_first():
    top = make_retriever().retrieve("offscreen images lazy", k=1)[0]
    assert top.heading == "Lazy load images"


def test_rag_adds_sources_to_prompt_and_baseline_does_not():
    reply = json.dumps({"diagnosis": "x", "fix": "inline critical css", "code": "",
                        "sources_used": [1]})
    finding = FindingInput("https://a.com", "render-blocking-resources",
                           "Eliminate render-blocking resources", "stylesheets block paint", 900)
    llm = ScriptedLLM([reply, reply])
    with_rag = suggest_fix(finding, llm, make_retriever(), use_rag=True, k=2)
    without = suggest_fix(finding, llm, make_retriever(), use_rag=False)
    assert "[1] (web.dev/test)" in llm.prompts[0]
    assert "reference sources" not in llm.prompts[1]
    assert with_rag.used_rag and not without.used_rag
    assert with_rag.fix == "inline critical css" and with_rag.sources_used == [1]


def test_fenced_json_is_parsed():
    llm = ScriptedLLM(['```json\n{"diagnosis": "d", "fix": "f", "code": "", "sources_used": []}\n```'])
    s = suggest_fix(FindingInput("u", "a", "t"), llm, None, use_rag=False)
    assert s.fix == "f"


def test_eval_reports_both_modes():
    case = Case("c1", "https://a.com", "offscreen-images", "Defer offscreen images",
                "lazy load", "add loading=lazy")
    gen = json.dumps({"diagnosis": "d", "fix": "add loading=lazy", "code": "", "sources_used": []})
    judge_no = json.dumps({"acceptable": False, "reason": "vague"})
    judge_yes = json.dumps({"acceptable": True, "reason": "matches"})
    results, summary = run([case], ScriptedLLM([gen, gen]), ScriptedLLM([judge_no, judge_yes]),
                           make_retriever())
    assert summary["without_rag"]["accepted_rate"] == 0.0
    assert summary["with_rag"]["accepted_rate"] == 1.0
    assert "cost_per_request_usd" in summary["with_rag"]


def test_p95():
    assert p95([float(i) for i in range(1, 101)]) == 95.0
