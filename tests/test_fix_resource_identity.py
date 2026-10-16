"""The prompt has to say what a resource IS, not just where it is.

WHY THIS FILE EXISTS
Two fixes sn0wy generated for its own site were wrong, and both failed the same
way: the model knew a URL and knew what the page was built with, and quietly
assumed the two belonged together.

1. "unused-javascript" on the frontend bundle came back as "add `defer`". A no-op
   twice over: Vite emits `<script type="module">`, which is already deferred, and
   `defer` changes when a script runs, never how many of its bytes go unused.
2. "uses-text-compression" came back as nginx config. The flagged response was not
   served by the scanned page's host at all; it came from a FastAPI service on
   another host, and the page's platform guidance was applied to it anyway.

So these tests assert on the PROMPT and on the deterministic placement string
rather than on model output. Per ADR 021, anything a user is shown about where a
fix goes is a fixed string we can be held to, not something generated per request.
"""

from __future__ import annotations

import json

import pytest

from core.fixes.context import (
    AUDIT_GUIDES,
    CROSS_HOST_PLACEMENT,
    Offender,
    Platform,
    foreign_host,
    placement,
    url_host,
)
from core.fixes.suggest import FindingInput, suggest_fix
from core.llm import ScriptedLLM

PAGE = "https://www.sn0wy.dev/"
API = "https://api.sn0wy.dev"


def _reply(**kw) -> str:
    return json.dumps({"diagnosis": "d", "fix": "f", "code": "", "sources_used": [], **kw})


def _prompt_for(finding: FindingInput) -> str:
    llm = ScriptedLLM([_reply()])
    suggest_fix(finding, llm, None, use_rag=False)
    return llm.prompts[0]


# ------------------------------------------------------- unused-javascript ----

def test_unused_js_guide_rules_out_defer():
    """The guide must actively deny the wrong answer, not merely omit it.

    The old text said "code-split, remove dead libraries, or defer third-party
    scripts", and the model took the word it recognised. Listing the right answer
    alongside a wrong one is not enough.
    """
    guide = AUDIT_GUIDES["unused-javascript"]
    assert "defer" in guide.lower()
    assert "do not" in guide.lower() or "does not" in guide.lower()
    # Says why, in terms of what the audit actually measures.
    assert "bytes" in guide.lower()


def test_unused_js_guide_says_module_scripts_are_already_deferred():
    guide = AUDIT_GUIDES["unused-javascript"]
    assert 'type="module"' in guide
    assert "already deferred" in guide


def test_unused_js_guide_names_code_splitting_for_first_party_bundles():
    guide = AUDIT_GUIDES["unused-javascript"]
    assert "code" in guide.lower() and "splitting" in guide.lower()
    assert "first-party" in guide.lower()


def test_unused_js_guide_reaches_the_prompt():
    p = _prompt_for(FindingInput(PAGE, "unused-javascript", "Reduce unused JavaScript"))
    assert "BYTES, not timing" in p
    assert "already deferred" in p


# ------------------------------------------------------------- host scope -----

def test_url_host():
    assert url_host("https://api.sn0wy.dev/stats") == "api.sn0wy.dev"
    assert url_host("not a url") is None


def test_foreign_host_detects_a_resource_on_another_host():
    offenders = [Offender(url=f"{API}/stats", wasted_kb=3.0)]
    assert foreign_host(PAGE, offenders) == "api.sn0wy.dev"


def test_foreign_host_is_none_for_the_pages_own_resources():
    offenders = [Offender(url=f"{PAGE}assets/index-abc.js", wasted_kb=60.0)]
    assert foreign_host(PAGE, offenders) is None


def test_foreign_host_is_strict_about_subdomains():
    """api.example.com and www.example.com are one owner but not one deployment.

    This is the case that produced the bad fix, so comparing registrable domains
    instead of hosts would miss exactly the bug this exists for.
    """
    assert foreign_host("https://www.example.com/", [Offender(url="https://api.example.com/x")])


def test_foreign_host_is_none_when_offenders_are_mixed():
    """A finding spanning both hosts keeps the page's guidance, where it is still
    partly right. This only fires when none of it applies."""
    offenders = [
        Offender(url=f"{PAGE}assets/a.js"),
        Offender(url=f"{API}/stats"),
    ]
    assert foreign_host(PAGE, offenders) is None


def test_foreign_host_is_none_without_offenders():
    assert foreign_host(PAGE, []) is None


@pytest.mark.parametrize("bad", ["", "not a url", "/relative/path"])
def test_foreign_host_tolerates_unusable_page_urls(bad):
    assert foreign_host(bad, [Offender(url=f"{API}/stats")]) is None


# --------------------------------------------------------- placement scope ----

def test_placement_stops_giving_the_pages_server_config_for_another_host():
    """The actual reported bug: nginx advice aimed at a FastAPI service."""
    same_host = placement("custom", "uses-text-compression")
    assert "nginx" in same_host  # unchanged for the page's own resources

    cross = placement("custom", "uses-text-compression", host="api.sn0wy.dev")
    assert "nginx" not in cross
    assert "api.sn0wy.dev" in cross
    assert cross == CROSS_HOST_PLACEMENT.format(host="api.sn0wy.dev")


def test_cross_host_placement_overrides_every_platform():
    """It is about the host, so the page's stack cannot change the answer."""
    answers = {
        placement(pid, "uses-text-compression", host="api.sn0wy.dev")
        for pid in ("custom", "shopify", "wordpress", "nextjs", None)
    }
    assert len(answers) == 1


def test_placement_unchanged_when_no_foreign_host():
    for pid in ("custom", "shopify", "wordpress", "nextjs", None):
        for audit in ("uses-text-compression", "unused-javascript", "modern-image-formats"):
            assert placement(pid, audit, host=None) == placement(pid, audit)


# ------------------------------------------------------------ the prompt ------

def test_prompt_flags_a_cross_host_offender_and_scopes_the_platform():
    finding = FindingInput(
        PAGE, "uses-text-compression", "Enable text compression", "d", 300,
        offenders=[Offender(url=f"{API}/stats", wasted_kb=3.0)],
        platform=Platform("custom", "Custom / no framework detected"),
    )
    p = _prompt_for(finding)

    # The resource line itself names the host and says it is not the page's.
    assert "served by api.sn0wy.dev, NOT the scanned page's host www.sn0wy.dev" in p
    # And it is spelled out, because one parenthetical did not stop the last one.
    assert "every resource above is served by api.sn0wy.dev" in p
    assert "say nothing about how api.sn0wy.dev is built" in p
    # The placement line no longer points at the page's own server config.
    assert "nginx" not in p


def test_prompt_says_nothing_extra_for_the_pages_own_resources():
    """No warning where there is nothing to warn about: the note would otherwise be
    noise on the common case and train the model to ignore it."""
    finding = FindingInput(
        PAGE, "unused-javascript", "Reduce unused JavaScript", "d", 900,
        offenders=[Offender(url=f"{PAGE}assets/index-abc.js", wasted_kb=60.0)],
        platform=Platform("custom", "Custom / no framework detected"),
    )
    p = _prompt_for(finding)
    assert "NOT the scanned page's host" not in p
    assert "IMPORTANT: every resource above" not in p


def test_prompt_marks_the_odd_one_out_in_a_mixed_finding():
    finding = FindingInput(
        PAGE, "unused-javascript", "Reduce unused JavaScript", "d", 900,
        offenders=[
            Offender(url=f"{PAGE}assets/index-abc.js", wasted_kb=60.0),
            Offender(url="https://cdn.vendor.test/widget.js", wasted_kb=40.0),
        ],
        platform=Platform("custom", "Custom / no framework detected"),
    )
    p = _prompt_for(finding)
    # Per-resource tag still fires for the foreign one...
    assert "served by cdn.vendor.test, NOT the scanned page's host www.sn0wy.dev" in p
    # ...but the blanket note does not, because the page's guidance still applies
    # to the first resource.
    assert "IMPORTANT: every resource above" not in p


def test_prompt_rule_scopes_the_platform_to_the_pages_host():
    p = _prompt_for(FindingInput(PAGE, "unused-javascript", "t"))
    assert "describes the scanned page's own host" in p
    assert "config file for a server you have not" in p


def test_where_shown_to_the_user_matches_the_cross_host_placement():
    """`where` is what the UI renders, so it has to carry the same correction."""
    llm = ScriptedLLM([_reply()])
    finding = FindingInput(
        PAGE, "uses-text-compression", "Enable text compression", "d", 300,
        offenders=[Offender(url=f"{API}/stats", wasted_kb=3.0)],
        platform=Platform("custom", "Custom / no framework detected"),
    )
    s = suggest_fix(finding, llm, None, use_rag=False)
    assert s.where == CROSS_HOST_PLACEMENT.format(host="api.sn0wy.dev")
    assert "nginx" not in s.where
