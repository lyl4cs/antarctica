"""Fix verification: flag site URLs in a fix that the audit never saw."""

import json

from core.fixes.context import Offender
from core.fixes.suggest import FindingInput, suggest_fix
from core.fixes.verify import unverified_urls
from core.llm import ScriptedLLM

PAGE = "https://shop.test/"
OFFS = [Offender("https://shop.test/assets/img/hero.jpg", 300.0),
        Offender("https://shop.test/assets/img/serum.jpg?v=2", 100.0)]


def test_invented_folder_is_flagged():
    code = '<img src="https://shop.test/images/hero.jpg">'
    assert unverified_urls(code, PAGE, OFFS) == ["https://shop.test/images/hero.jpg"]


def test_real_file_and_new_sibling_are_allowed():
    code = ('<picture><source srcset="https://shop.test/assets/img/hero.webp" type="image/webp">'
            '<img src="https://shop.test/assets/img/hero.jpg"></picture>')
    assert unverified_urls(code, PAGE, OFFS) == []


def test_root_relative_paths_checked_too():
    assert unverified_urls('<img src="/assets/img/hero.avif">', PAGE, OFFS) == []
    assert unverified_urls("<img src='/img/hero.avif'>", PAGE, OFFS) == ["/img/hero.avif"]


def test_other_hosts_and_docs_links_are_not_claims_about_the_site():
    text = "See https://web.dev/articles/serve-images-webp and https://cdn.other.test/x/y.js."
    assert unverified_urls(text, PAGE, OFFS) == []


def test_no_offenders_means_nothing_to_check():
    assert unverified_urls('<img src="https://shop.test/whatever/x.jpg">', PAGE, []) == []


def test_dedupes_and_strips_trailing_punctuation():
    text = "Use https://shop.test/images/a.jpg. Then https://shop.test/images/a.jpg again"
    assert unverified_urls(text, PAGE, OFFS) == ["https://shop.test/images/a.jpg"]


def test_suggest_fix_reports_unverified_urls():
    reply = json.dumps({"diagnosis": "d", "fix": "convert hero",
                        "code": '<img src="https://shop.test/images/hero.webp">',
                        "sources_used": []})
    s = suggest_fix(FindingInput(PAGE, "modern-image-formats", "t", offenders=OFFS),
                    ScriptedLLM([reply]), None, use_rag=False)
    assert s.unverified_urls == ["https://shop.test/images/hero.webp"]


def test_prompt_forbids_commented_out_code():
    llm = ScriptedLLM([json.dumps({"diagnosis": "", "fix": "", "code": "", "sources_used": []})])
    suggest_fix(FindingInput(PAGE, "a", "t", offenders=OFFS), llm, None, use_rag=False)
    p = llm.prompts[0]
    assert "no commented-out code" in p and "SAME folder" in p
