"""The scanner image must pin both halves of the measuring engine.

A Lighthouse score is only comparable to another score measured the same way.
Lighthouse computes the number, but Chromium produces the trace it computes from,
so a browser that moves underneath you shifts scores exactly like a Lighthouse
upgrade would. ADR 022 made that argument and the Dockerfile applied it to
Lighthouse only, leaving `apt-get install chromium` unpinned.

The cost was not hypothetical. The image went a long time without a rebuild, so
the rebuild that bumped Lighthouse to 12.8.2 also pulled whatever Chromium Debian
shipped that day, and the scanner died on every request. Two variables changed in
one deploy and neither was written down.

These tests read the build files as text. They cannot build an image, so they
check the thing that actually regressed: that the pinning mechanism exists and is
wired end to end, and that nobody has quietly gone back to a floating version.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "services" / "scanner" / "Dockerfile"
CLOUDBUILD = ROOT / "infra" / "cloudbuild.yaml"
DEPLOY = ROOT / "infra" / "deploy.sh"


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text()


# ------------------------------------------------------------------ lighthouse --

def test_lighthouse_is_pinned_to_an_exact_version(dockerfile):
    m = re.search(r"npm install -g lighthouse@([^\s\\]+)", dockerfile)
    assert m, "the scanner image must install lighthouse"
    version = m.group(1)
    # "12" or "^12.8.2" would float on rebuild, which is the whole problem.
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"lighthouse must be pinned exactly, got {version!r}"
    )


# -------------------------------------------------------------------- chromium --

def test_chromium_version_is_a_build_arg(dockerfile):
    assert re.search(r"^ARG CHROMIUM_VERSION", dockerfile, re.MULTILINE), (
        "the browser must be pinnable, not whatever Debian ships on build day"
    )


def test_a_pinned_chromium_version_is_actually_used(dockerfile):
    """Declaring the ARG is not enough; the install has to honour it."""
    assert 'chromium=$CHROMIUM_VERSION' in dockerfile


def test_the_build_records_the_browser_it_shipped(dockerfile):
    """Without this, answering "what Chrome ran that scan" needs the image itself."""
    assert "chromium --version" in dockerfile


def test_the_base_image_names_its_debian_release(dockerfile):
    """`python:3.12-slim` follows Debian stable, so the distro can change on its
    own schedule and take the browser with it."""
    m = re.search(r"^FROM (\S+)", dockerfile, re.MULTILINE)
    assert m
    assert re.search(r"-(bookworm|bullseye|trixie)$", m.group(1)), (
        f"base image should name its Debian release, got {m.group(1)!r}"
    )


# -------------------------------------------------------------------- plumbing --

def test_cloudbuild_passes_the_version_through():
    text = CLOUDBUILD.read_text()
    assert "CHROMIUM_VERSION=${_CHROMIUM_VERSION}" in text
    assert "_CHROMIUM_VERSION" in text.split("substitutions:")[1], (
        "the substitution needs a default or a build without it fails"
    )


def test_deploy_script_forwards_the_version():
    """End of the chain: CHROMIUM_VERSION=... bash infra/deploy.sh has to reach
    the build. A pin nobody can set is not a pin."""
    assert "_CHROMIUM_VERSION=${CHROMIUM_VERSION:-}" in DEPLOY.read_text()


# --------------------------------------------------- frontend security headers --
# Vercel serves the React app, so its headers live in vercel.json rather than in
# any code path a Python test can exercise. Checked as config, like the Dockerfile
# above: the point is that nobody quietly drops one.

def test_vercel_sets_the_security_headers():
    import json

    cfg = json.loads((ROOT / "frontend" / "vercel.json").read_text())
    glob = next(r for r in cfg["headers"] if r["source"] == "/(.*)")
    keys = {h["key"] for h in glob["headers"]}
    assert {
        "Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy",
        "X-Frame-Options", "Strict-Transport-Security", "Permissions-Policy",
    } <= keys


def test_the_csp_allows_the_data_font_vite_inlines():
    """Vite inlines assets under 4096 bytes and one woff2 subset lands under it,
    so font-src 'self' alone silently drops a typeface in production. Found by
    loading the built app under the real policy, not by reading the config."""
    import json

    cfg = json.loads((ROOT / "frontend" / "vercel.json").read_text())
    csp = next(h["value"] for r in cfg["headers"] for h in r["headers"]
               if h["key"] == "Content-Security-Policy")
    assert "font-src 'self' data:" in csp


def test_the_csp_closes_the_dangerous_defaults():
    import json

    cfg = json.loads((ROOT / "frontend" / "vercel.json").read_text())
    csp = next(h["value"] for r in cfg["headers"] for h in r["headers"]
               if h["key"] == "Content-Security-Policy")
    for directive in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'"):
        assert directive in csp
