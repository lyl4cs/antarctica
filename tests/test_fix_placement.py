"""Placement: the deterministic "which file do I edit" line on every fix.

The point of these tests is that placement is NOT model output. It comes from a
hand-written table keyed by (platform, audit category), so a fix can never invent
a path inside a repo nobody has seen. See core/fixes/context.py.
"""

import pytest

from core.fixes.context import (
    AUDIT_CATEGORY,
    AUDIT_GUIDES,
    GENERIC_PLACEMENT,
    PLACEMENT,
    Platform,
    placement,
)
from core.fixes.suggest import FindingInput, suggest_fix
from core.llm import ScriptedLLM

SITE = "https://shop.test"


def test_platform_changes_where_the_same_audit_goes():
    """The whole feature in one assertion: same problem, different file per stack."""
    audit = "modern-image-formats"
    shopify = placement("shopify", audit)
    wordpress = placement("wordpress", audit)
    nextjs = placement("nextjs", audit)
    assert "Themes > Edit code" in shopify
    assert "theme" in wordpress and "plugin" in wordpress
    assert "next/image" in nextjs
    assert len({shopify, wordpress, nextjs}) == 3


def test_category_changes_where_within_one_platform():
    assert placement("nextjs", "modern-image-formats") != placement("nextjs", "unused-javascript")
    assert "next/dynamic" in placement("nextjs", "unused-javascript")


def test_unknown_audit_falls_back_to_the_platform_default():
    assert placement("shopify", "some-future-audit") == PLACEMENT["shopify"]["_default"]


def test_unknown_platform_falls_back_to_custom():
    assert placement("plan9", "unused-javascript") == PLACEMENT["custom"]["js"]
    assert placement(None, "unused-javascript") == PLACEMENT["custom"]["js"]


def test_always_returns_something_for_every_known_audit():
    """A fix must never render an empty 'where' line."""
    for platform_id in [*PLACEMENT, "unknown-platform", None]:
        for audit_id in [*AUDIT_GUIDES, "not-an-audit"]:
            assert placement(platform_id, audit_id).strip()


def test_hosted_shopify_is_honest_about_what_you_cannot_change():
    """Server fixes are impossible on hosted Shopify; saying so beats a fake fix."""
    where = placement("shopify", "server-response-time")
    assert "not yours to change" in where


def test_shopify_integration_points_at_your_own_template_not_the_theme():
    where = placement("shopify-integration", "modern-image-formats")
    assert "your own template" in where.lower()
    assert where != placement("shopify", "modern-image-formats")


def test_every_categorised_audit_is_a_real_audit_guide():
    """Typos in AUDIT_CATEGORY would silently downgrade a fix to the default."""
    assert set(AUDIT_CATEGORY) <= set(AUDIT_GUIDES)


def test_every_table_category_is_one_a_real_audit_maps_to():
    """A category no audit uses is dead text; catch it instead of shipping it."""
    live = set(AUDIT_CATEGORY.values()) | {"_default"}
    for platform_id, table in PLACEMENT.items():
        unreachable = set(table) - live
        assert not unreachable, f"{platform_id} has unreachable categories {unreachable}"


@pytest.mark.parametrize("platform_id,expected", [
    ("shopify", "layout/theme.liquid"),
    ("wordpress", "CHILD theme"),
    ("custom", "bundler config"),
])
def test_placement_reaches_the_prompt_and_the_suggestion(platform_id, expected):
    """It goes to the model as context AND comes back as a field, unchanged."""
    llm = ScriptedLLM(['{"diagnosis":"d","fix":"f","code":"","sources_used":[]}'])
    finding = FindingInput(
        SITE, "unused-javascript", "Reduce unused JavaScript",
        platform=Platform(platform_id, platform_id),
    )
    s = suggest_fix(finding, llm, retriever=None, use_rag=False)

    assert "Where to put it:" in llm.prompts[0]
    assert expected in llm.prompts[0]
    assert s.where == placement(platform_id, "unused-javascript")
    assert expected in s.where


def test_no_platform_still_gets_a_generic_line():
    llm = ScriptedLLM(['{"diagnosis":"d","fix":"f","code":"","sources_used":[]}'])
    s = suggest_fix(FindingInput(SITE, "total-byte-weight", "Heavy page"),
                    llm, retriever=None, use_rag=False)
    assert s.where == GENERIC_PLACEMENT
