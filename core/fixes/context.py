"""Evidence the fix prompt needs, pulled from the raw Lighthouse result.

WHY THIS EXISTS (v1 -> v2)
v1 gave Gemini only a finding's title and description, so it answered with
generic code (`flower.jpg`, `path/to/image.jpg`) and guessed at the site's stack.
Lighthouse already knows much more, and we store its full JSON for every scan:

1. OFFENDERS: for each finding, the exact resources responsible and how much each
   wastes (`audits[<id>].details.items`). Fixes can name the real files.
2. PLATFORM: what the site is built on, from evidence, never assumed:
   - Lighthouse's own "stack packs" (it detects WordPress, Next.js, React, Wix...)
   - URL fingerprints in the page's network requests (`/wp-content/`, `/_next/`,
     `cdn.shopify.com`...). A site that merely LOADS Shopify assets (e.g. product
     images or a Buy Button) is labelled as an integration, not a Shopify store,
     because the right fix differs.
3. AUDIT GUIDES: one line per audit on what it actually measures, so the model
   doesn't answer "efficiently encode images" (compression) with the
   "next-gen formats" (WebP) fix.

Everything here is pure and works on the full raw JSON or on the slim subset the
store extracts (see `slim_lhr`), so the same code runs in tests, the API and evals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

MAX_OFFENDERS = 5


@dataclass
class Offender:
    url: str
    wasted_kb: float | None = None
    wasted_ms: float | None = None
    total_kb: float | None = None


@dataclass
class Platform:
    id: str                    # "wordpress", "nextjs", "shopify", "custom", ...
    name: str                  # human label
    evidence: list[str] = field(default_factory=list)
    guidance: str = ""         # platform-specific advice for the prompt

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- offenders --

def _item_url(item: dict) -> str | None:
    url = item.get("url")
    if isinstance(url, str):
        return url
    src = item.get("source") or item.get("node") or {}
    if isinstance(src, dict) and isinstance(src.get("url"), str):
        return src["url"]
    return None


def extract_offenders(lhr: dict, audit_id: str, n: int = MAX_OFFENDERS) -> list[Offender]:
    """Top-n resources behind one finding, biggest waste first. [] if none listed."""
    items = (((lhr.get("audits") or {}).get(audit_id) or {}).get("details") or {}).get("items")
    out: list[Offender] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = _item_url(item)
        if not url or url.startswith("data:"):
            continue
        wb, wm, tb = item.get("wastedBytes"), item.get("wastedMs"), item.get("totalBytes")
        out.append(Offender(
            url=url,
            wasted_kb=None if wb is None else round(wb / 1024, 1),
            wasted_ms=None if wm is None else round(wm),
            total_kb=None if tb is None else round(tb / 1024, 1),
        ))
    out.sort(key=lambda o: (o.wasted_kb or 0, o.wasted_ms or 0), reverse=True)
    return out[:n]


# ----------------------------------------------------------------- platform --

# Lighthouse stack-pack id -> (our id, label). Lighthouse detects these itself.
STACK_PACKS = {
    "wordpress": ("wordpress", "WordPress"), "next.js": ("nextjs", "Next.js"),
    "nextjs": ("nextjs", "Next.js"), "nuxt": ("nuxt", "Nuxt"), "gatsby": ("gatsby", "Gatsby"),
    "react": ("react", "React"), "angular": ("angular", "Angular"), "wix": ("wix", "Wix"),
    "drupal": ("drupal", "Drupal"), "joomla": ("joomla", "Joomla"),
    "magento": ("magento", "Magento"), "amp": ("amp", "AMP"),
}

# (substring in a request URL, our id, label), checked in order; first match wins
# per platform. Hosted-Shopify markers are separate from "loads Shopify assets".
URL_FINGERPRINTS = [
    ("/wp-content/", "wordpress", "WordPress"),
    ("/wp-includes/", "wordpress", "WordPress"),
    ("/_next/static/", "nextjs", "Next.js"),
    ("/_nuxt/", "nuxt", "Nuxt"),
    ("static.wixstatic.com", "wix", "Wix"),
    ("squarespace-cdn.com", "squarespace", "Squarespace"),
    ("static1.squarespace.com", "squarespace", "Squarespace"),
    ("website-files.com", "webflow", "Webflow"),
    ("framerusercontent.com", "framer", "Framer"),
    ("/cdn/shop/", "shopify", "Shopify (hosted store)"),
    ("/cdn/shopifycloud/", "shopify", "Shopify (hosted store)"),
]
SHOPIFY_ASSET_HOSTS = ("cdn.shopify.com", "sdks.shopifycdn.com", "shopifycdn.com")

GUIDANCE = {
    "wordpress": "Prefer plugin/theme-level fixes (functions.php, a caching or image "
                 "plugin) over editing generated HTML.",
    "nextjs": "Prefer framework features: next/image (sizes, priority on the LCP "
              "image), next/font, dynamic() imports, next/script strategy.",
    "nuxt": "Prefer framework features: @nuxt/image, lazy components, nuxt.config "
            "build options.",
    "shopify": "This is a hosted Shopify theme: fix it in Liquid (e.g. "
               "`image_url: width:` + `image_tag` with widths/sizes, which also "
               "serves WebP/AVIF automatically) and theme settings, not server config.",
    "shopify-integration": "The page loads assets from Shopify's CDN but is not a "
                           "Shopify theme. Images on cdn.shopify.com can be resized "
                           "and converted by URL parameters (e.g. `?width=800`), "
                           "so fixes can point the site's HTML at sized URLs.",
    "wix": "Wix limits code access: prefer editor settings and image optimization "
           "options; say when a fix is not possible on the platform.",
    "squarespace": "Squarespace limits code access: prefer image size settings and "
                   "code injection only when needed.",
    "webflow": "Prefer Webflow Designer settings (responsive images, lazy loading, "
               "custom code in page settings).",
    "custom": "No framework detected: give plain HTML/CSS/JS or web-server fixes "
              "(e.g. nginx/Apache headers) using the real resource URLs.",
}


def _request_urls(lhr: dict) -> list[str]:
    items = ((((lhr.get("audits") or {}).get("network-requests") or {})
              .get("details") or {}).get("items")) or []
    return [i["url"] for i in items if isinstance(i, dict) and isinstance(i.get("url"), str)]


def detect_platform(lhr: dict) -> Platform:
    """What the site is built on, with the evidence. 'custom' if nothing matches."""
    found: dict[str, Platform] = {}

    for pack in lhr.get("stackPacks") or []:
        pid = str(pack.get("id", "")).lower()
        if pid in STACK_PACKS:
            our_id, label = STACK_PACKS[pid]
            found.setdefault(our_id, Platform(our_id, label)).evidence.append(
                f"Lighthouse detected {pack.get('title') or label}")

    urls = _request_urls(lhr)
    url_matched: set[str] = set()  # one URL piece of evidence per platform is enough
    for needle, our_id, label in URL_FINGERPRINTS:
        hit = next((u for u in urls if needle in u), None)
        if hit and our_id not in url_matched:
            url_matched.add(our_id)
            found.setdefault(our_id, Platform(our_id, label)).evidence.append(
                f"requests {needle} ({_short(hit)})")

    if "shopify" not in found:
        hit = next((u for u in urls if urlparse(u).hostname
                    and urlparse(u).hostname.endswith(SHOPIFY_ASSET_HOSTS)), None)
        if hit:
            found["shopify-integration"] = Platform(
                "shopify-integration", "Custom site + Shopify assets",
                [f"loads {_short(hit)}"])

    # Most specific first: a framework/CMS beats plain React; React beats nothing.
    order = ["shopify", "wordpress", "nextjs", "nuxt", "gatsby", "wix", "squarespace",
             "webflow", "framer", "drupal", "joomla", "magento", "angular",
             "shopify-integration", "react", "amp"]
    chosen = next((found[k] for k in order if k in found), None)
    if chosen is None:
        chosen = Platform("custom", "Custom / no framework detected",
                          ["no known framework or CMS fingerprints in requests"])
    others = [p.name for k, p in found.items() if p is not chosen]
    if others:
        chosen.evidence.append("also detected: " + ", ".join(others))
    chosen.guidance = GUIDANCE.get(
        chosen.id,
        f"The site uses {chosen.name}: prefer fixes that fit how {chosen.name} builds "
        "pages, and use the real resource URLs.")
    return chosen


def platform_from_dict(d: dict | None) -> Platform | None:
    """Rebuild a Platform (with its prompt guidance) from the API/eval JSON form,
    which carries only id, name and evidence."""
    if not d:
        return None
    p = Platform(d["id"], d.get("name", d["id"]), list(d.get("evidence", [])))
    p.guidance = GUIDANCE.get(p.id, f"The site uses {p.name}: prefer fixes that fit how "
                                    f"{p.name} builds pages, and use the real resource URLs.")
    return p


def _short(url: str, n: int = 80) -> str:
    return url if len(url) <= n else url[: n - 1] + "…"


# ------------------------------------------------------------- audit guides --

AUDIT_GUIDES = {
    "modern-image-formats": "FORMAT only: serve WebP/AVIF instead of JPEG/PNG. Not about "
                            "dimensions or compression level.",
    "uses-optimized-images": "COMPRESSION only: re-encode the same format at a lower "
                             "quality (e.g. JPEG q~80) or strip metadata. Not a format "
                             "change, not resizing.",
    "uses-responsive-images": "DIMENSIONS: images are larger than their displayed size. "
                              "Serve sized variants (srcset/sizes or resized URLs).",
    "offscreen-images": "Below-the-fold images load too early: lazy-load them "
                        "(loading=\"lazy\"); never lazy-load the LCP image.",
    "render-blocking-resources": "CSS/JS in <head> delays first paint: inline critical "
                                 "CSS, defer/async scripts, load the rest later.",
    "unused-javascript": "JS downloaded but not executed: code-split, remove dead "
                         "libraries, or defer third-party scripts.",
    "unused-css-rules": "CSS rules that never apply on this page: purge or split "
                        "stylesheets per page.",
    "uses-text-compression": "Text responses sent uncompressed: enable gzip/brotli on the "
                             "server or CDN.",
    "uses-long-cache-ttl": "Static assets have short cache lifetimes: set long "
                           "Cache-Control max-age with hashed filenames.",
    "server-response-time": "Slow time to first byte from the server: caching, CDN, or "
                            "backend work. Not a front-end code change.",
    "unminified-javascript": "Minify JS in the build.",
    "unminified-css": "Minify CSS in the build.",
    "efficient-animated-content": "Large animated GIFs: replace with muted looping "
                                  "MP4/WebM video.",
    "legacy-javascript": "Polyfills/transpiled code shipped to modern browsers: target "
                         "modern browsers in the build.",
    "duplicated-javascript": "Same module bundled more than once: dedupe dependencies.",
    "prioritize-lcp-image": "Preload / fetchpriority=\"high\" the LCP image.",
    "uses-rel-preconnect": "Add <link rel=\"preconnect\"> to required third-party origins.",
    "font-display": "Text invisible while fonts load: use font-display: swap.",
    "total-byte-weight": "Page is heavy overall: find the biggest resources and cut them.",
    "redirects": "Page redirects before loading: link to the final URL.",
}


def audit_guide(audit_id: str) -> str:
    return AUDIT_GUIDES.get(audit_id, "")


# ------------------------------------------------------------- slim extract --

def slim_lhr(lhr: dict, audit_ids: list[str]) -> dict:
    """Only the parts of a raw report this module reads (for an in-memory store).
    The Postgres store builds the same shape in SQL so it never ships the full JSON."""
    audits = lhr.get("audits") or {}
    keep = {a: {"details": {"items": ((audits.get(a) or {}).get("details") or {}).get("items")}}
            for a in [*audit_ids, "network-requests"] if a in audits}
    return {"stackPacks": lhr.get("stackPacks") or [], "audits": keep}
