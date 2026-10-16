"""Building an eval set: drafted answer keys, and the gate that keeps them drafts.

The eval's whole value is that a person wrote the answer key. These tests cover the
two halves of that: a draft is specific enough to be worth reviewing, and nothing
reaches a reported number without someone having approved it.
"""

import json
from pathlib import Path

import pytest

from core.evals.references import REFERENCES, doc_for, draft_reference
from core.evals.run_eval import load_cases
from scripts.build_cases import read_ids
from scripts.review_cases import load, needs_review, promote, render, reviewed, save

CASE = {
    "id": "case-001",
    "url": "https://shop.test/",
    "audit_id": "unused-javascript",
    "title": "Reduce unused JavaScript",
    "description": "",
    "savings_ms": 1200,
    "offenders": [{"url": "https://shop.test/assets/index-a1b2.js", "wasted_kb": 47.8}],
    "platform": None,
    "reference_fix": "",
    "reference_draft": "Ship less of the offending bundle: ... Offending resources: index-a1b2.js.",
}


# --------------------------------------------------------------------- drafts --

def test_draft_names_the_files_this_scan_blamed():
    """A reference that could be pasted onto any site would accept a generic answer,
    which is the failure the eval exists to catch."""
    d = draft_reference("modern-image-formats", [{"url": "https://s.test/img/hero.jpg"}])
    assert "hero.jpg" in d


def test_draft_is_deterministic():
    args = ("unused-css-rules", [{"url": "https://s.test/a.css"}])
    assert draft_reference(*args) == draft_reference(*args)


def test_unknown_audit_gets_no_draft():
    """Better a blank the reviewer must fill than a plausible guess they'd skim past."""
    assert draft_reference("some-audit-we-have-no-entry-for", []) == ""


def test_draft_for_unused_js_does_not_recommend_defer():
    """The regression that started this: `defer` does not reduce unused bytes, and a
    reference saying otherwise would grade the wrong answer as correct (ADR 023)."""
    d = draft_reference("unused-javascript", [{"url": "https://s.test/app.js"}]).lower()
    assert "split" in d
    # the only mention of deferring is the sentence ruling it out
    assert "deferring does not reduce unused bytes" in d


def test_draft_survives_an_offender_with_no_filename():
    assert draft_reference("server-response-time", [{"url": "https://s.test/"}])


def test_every_reference_points_at_a_doc_in_the_rag_corpus():
    """The reviewer checks the draft against `doc`. If that page isn't one of the
    pages we ingested, the reference and the retrieval disagree about the source."""
    corpus = set(Path("scripts/doc_urls.txt").read_text().split())
    for audit_id, ref in REFERENCES.items():
        assert ref.doc in corpus, f"{audit_id} cites {ref.doc}, which is not in doc_urls.txt"


def test_doc_for_unknown_audit_is_empty():
    assert doc_for("not-an-audit") == ""


# --------------------------------------------------------------------- review --

def test_a_drafted_case_still_needs_review():
    assert needs_review(CASE)


def test_promote_sets_the_fix_and_drops_the_draft():
    """The draft is removed, not kept beside it: nobody should later have to work out
    which of two strings was the approved one."""
    out = promote(CASE, "Split the bundle by route.")
    assert out["reference_fix"] == "Split the bundle by route."
    assert "reference_draft" not in out
    assert not needs_review(out)


def test_promote_refuses_an_empty_fix():
    with pytest.raises(ValueError):
        promote(CASE, "   ")


def test_export_keeps_only_approved_cases():
    approved = promote({**CASE, "id": "case-002"}, "Enable gzip.")
    assert [c["id"] for c in reviewed([CASE, approved])] == ["case-002"]


def test_review_round_trips_through_the_file(tmp_path):
    """The run is resumable, so a half-reviewed file has to survive save/load."""
    p = tmp_path / "cases.jsonl"
    save([CASE, promote({**CASE, "id": "case-002"}, "Enable gzip.")], p)
    assert [needs_review(c) for c in load(p)] == [True, False]


def test_render_shows_the_offenders_the_draft_named():
    """A reviewer can only judge "did it name the right files" if they see the files."""
    text = render(CASE)
    assert "index-a1b2.js" in text
    assert "developer.chrome.com" in text


# ----------------------------------------------------------------- the gate --

def test_load_cases_refuses_an_unreviewed_case(tmp_path):
    p = tmp_path / "cases.jsonl"
    p.write_text(json.dumps(CASE) + "\n")
    with pytest.raises(ValueError, match="no reference_fix"):
        load_cases(p)


def test_load_cases_ignores_the_draft_field(tmp_path):
    """A partly reviewed draft file is a normal thing to have on disk."""
    p = tmp_path / "cases.jsonl"
    p.write_text(json.dumps(promote(CASE, "Split the bundle by route.")) + "\n")
    [case] = load_cases(p)
    assert case.reference_fix == "Split the bundle by route."
    assert case.offenders[0]["wasted_kb"] == 47.8


def test_load_cases_skips_blank_lines(tmp_path):
    p = tmp_path / "cases.jsonl"
    p.write_text(json.dumps(promote(CASE, "x")) + "\n\n")
    assert len(load_cases(p)) == 1


# ------------------------------------------------------------------- ids in --

def test_ids_come_from_stdin_when_asked():
    """So a list pasted out of the database goes straight in."""
    assert read_ids(["-"], "a\n b \n\nc\n") == ["a", "b", "c"]


def test_ids_otherwise_come_from_the_command_line():
    assert read_ids(["a", "b"], "ignored") == ["a", "b"]
