"""Draft reference fixes, so building an eval set takes an afternoon, not a weekend.

WHAT A REFERENCE FIX IS
`run_eval` grades every generated fix against a `reference_fix`: the remedy a
person has confirmed is correct for that finding. The eval is worth exactly what
that answer key is worth, so the answer key cannot be machine-written. If a model
wrote both sides, the number would measure a model agreeing with itself.

WHY THIS MODULE EXISTS ANYWAY
Writing thirty answers from a blank page is the reason an eval set never gets
built. So this writes a DRAFT: the canonical remedy for that audit, taken from the
docs, filled in with the files this scan actually blamed. The draft lands in
`reference_draft`. It is never written to `reference_fix`, and `load_cases`
refuses a case whose `reference_fix` is empty, so a draft cannot leak into a
reported number by being forgotten. The only thing that promotes a draft is a
person pressing a key in `scripts/review_cases.py` with `doc` open beside them.

Machine drafts, human approves, eval grades. A draft waved through unread is a
wrong answer key and a wrong eval, which is why every entry carries the page to
check it against, and why those pages are the same ones in `scripts/doc_urls.txt`.

WHY A TABLE AND NOT A PROMPT
Same reasoning as ADR 021. A table is deterministic, reviewable in a diff, and
wrong in a way that is fixable for everyone at once. A drafted answer key that
varies per run is not an answer key.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

CHROME = "https://developer.chrome.com/docs/lighthouse/performance"
WEBDEV = "https://web.dev/articles"


@dataclass(frozen=True)
class Reference:
    """The remedy for one audit, and the page a reviewer should check it against."""

    remedy: str
    doc: str


# The remedy only. WHERE it goes is the placement table's job (ADR 021), and the
# wording deliberately keeps the distinctions AUDIT_GUIDES draws: a reference that
# blurred format vs compression would accept a fix that confuses them.
REFERENCES: dict[str, Reference] = {
    "modern-image-formats": Reference(
        "Re-encode the offending images as WebP or AVIF and serve them with a "
        "<picture> fallback, keeping the same dimensions and quality.",
        f"{WEBDEV}/serve-images-webp",
    ),
    "uses-optimized-images": Reference(
        "Re-encode the offending images in their existing format at a lower quality "
        "(around JPEG q80) and strip metadata. Not a format change and not a resize.",
        f"{WEBDEV}/uses-optimized-images",
    ),
    "uses-responsive-images": Reference(
        "Generate smaller variants of the offending images and serve them with "
        "srcset/sizes so each viewport downloads one close to its displayed size.",
        f"{WEBDEV}/serve-responsive-images",
    ),
    "offscreen-images": Reference(
        'Add loading="lazy" to the offending below-the-fold images. The LCP image '
        "must not be lazy-loaded.",
        f"{WEBDEV}/browser-level-image-lazy-loading",
    ),
    "render-blocking-resources": Reference(
        "Inline the critical CSS and load the rest asynchronously (rel=preload as=style, "
        "or media=print swapped onload); defer the blocking scripts.",
        f"{CHROME}/render-blocking-resources",
    ),
    "unused-javascript": Reference(
        "Ship less of the offending bundle: split it at the route or component level "
        "(dynamic import(), React.lazy) so code for other routes is a separate chunk, "
        "and drop dependencies the page never uses. Deferring does not reduce unused "
        "bytes. A third-party script is removed or loaded only where it is used.",
        f"{CHROME}/unused-javascript",
    ),
    "unused-css-rules": Reference(
        "Purge the rules this page never uses from the offending stylesheets, or split "
        "them so each page loads only its own.",
        f"{CHROME}/unused-css-rules",
    ),
    "uses-text-compression": Reference(
        "Enable gzip or brotli for text responses on whatever serves the offending "
        "resources: the server, framework middleware, or the CDN in front of it.",
        f"{WEBDEV}/reduce-network-payloads-using-text-compression",
    ),
    "uses-long-cache-ttl": Reference(
        "Serve the offending static assets with a long Cache-Control max-age and "
        "content-hashed filenames so a new build busts the cache.",
        f"{WEBDEV}/http-cache",
    ),
    "server-response-time": Reference(
        "Cut time to first byte on the server: cache the response, put a CDN in front "
        "of it, or make the slow backend work faster. Not a front-end change.",
        f"{CHROME}/server-response-time",
    ),
    "unminified-javascript": Reference(
        "Minify the offending JavaScript in the build step and ship the minified output.",
        f"{WEBDEV}/unminified-javascript",
    ),
    "unminified-css": Reference(
        "Minify the offending CSS in the build step and ship the minified output.",
        f"{WEBDEV}/unminified-javascript",
    ),
    "efficient-animated-content": Reference(
        "Replace the offending animated GIFs with muted, looping, autoplaying MP4 or "
        "WebM video.",
        f"{WEBDEV}/reduce-network-payloads-using-text-compression",
    ),
    "legacy-javascript": Reference(
        "Stop shipping polyfills and transpiled syntax modern browsers do not need: "
        "raise the build target (browserslist) so the offending bundles are built for "
        "modern browsers.",
        f"{WEBDEV}/remove-unused-code",
    ),
    "duplicated-javascript": Reference(
        "Dedupe the module that is bundled more than once: align the dependency "
        "versions so one copy is shared across the offending bundles.",
        f"{WEBDEV}/reduce-javascript-payloads-with-code-splitting",
    ),
    "prioritize-lcp-image": Reference(
        'Preload the LCP image and mark it fetchpriority="high" so it is discovered '
        "and fetched before lower-priority resources.",
        f"{WEBDEV}/fetch-priority",
    ),
    "uses-rel-preconnect": Reference(
        "Add <link rel=preconnect> for the third-party origins the page needs early, "
        "only for origins it genuinely uses.",
        f"{WEBDEV}/preconnect-and-dns-prefetch",
    ),
    "font-display": Reference(
        "Set font-display: swap on the offending @font-face rules so text renders in a "
        "fallback while the webfont loads.",
        f"{CHROME}/font-display",
    ),
    "total-byte-weight": Reference(
        "Cut the largest resources on the page: compress or resize the heaviest assets "
        "and stop shipping what the page does not use.",
        f"{WEBDEV}/remove-unused-code",
    ),
}


def _name(url: str) -> str:
    """Last path segment of a URL, which is the part a person recognises."""
    path = urlsplit(url).path
    return path.rstrip("/").rsplit("/", 1)[-1] or urlsplit(url).netloc or url


def draft_reference(
    audit_id: str, offenders: Sequence[Mapping[str, object]] = (), limit: int = 3
) -> str:
    """A draft answer key for one finding, or "" if this audit has no entry.

    The offenders are named so the draft is about THIS scan and not a generic
    paragraph. A reference that could be pasted onto any site would grade a
    generic answer as correct, which is the failure mode the eval exists to catch.
    An audit with no entry returns "", so the reviewer writes it from scratch
    rather than being handed a plausible-looking guess.
    """
    ref = REFERENCES.get(audit_id)
    if ref is None:
        return ""
    names = [_name(str(o["url"])) for o in offenders if o.get("url")][:limit]
    if not names:
        return ref.remedy
    return f"{ref.remedy} Offending resources: {', '.join(names)}."


def doc_for(audit_id: str) -> str:
    """The page a reviewer should check this audit's draft against."""
    ref = REFERENCES.get(audit_id)
    return ref.doc if ref else ""
