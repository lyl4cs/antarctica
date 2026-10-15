"""Check an AI fix against the audit evidence: did it invent file paths?

WHY
v2 gives the model the exact offending URLs and tells it never to invent paths.
Telling isn't checking. On shopnovus.us it wrote
`https://shopnovus.us/images/model-lifestyle.jpg`; whether `/images/` is real can
only be known by comparing with what Lighthouse actually saw.

HOW
- Pull every URL out of the fix text and code (absolute `https://...` URLs and
  root-relative "/path/file.ext" strings in quotes).
- Only judge URLs on the site's own hosts (the scanned page + the offenders'
  hosts). A link to web.dev or a CDN the site doesn't use is not a claim about
  the site.
- A URL is VERIFIED if its folder is one where the audit found a file. Same folder
  but a new name is allowed on purpose: `hero.webp` next to the real `hero.jpg`
  is exactly what a "convert to WebP" fix should propose.
- Everything else is returned as unverified, so the UI can warn "check these
  paths" instead of the user pasting a broken URL into production.

If the audit listed no offenders there's nothing to compare against, so nothing
is flagged (no evidence = no claim either way).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from core.fixes.context import Offender

ABSOLUTE = re.compile(r"https?://[^\s\"'<>`)\]]+")
ROOT_RELATIVE = re.compile(r"[\"'(](/[^\s\"'<>`)]+\.[A-Za-z0-9]{2,5})(?:\?[^\s\"'<>`)]*)?[\"')]")


def _folder(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def unverified_urls(text: str, page_url: str, offenders: list[Offender]) -> list[str]:
    """URLs in `text` on the site's hosts whose folder the audit never saw. Deduped, in order."""
    if not offenders:
        return []
    page_host = urlparse(page_url).hostname or ""
    hosts = {page_host} | {urlparse(o.url).hostname or "" for o in offenders}
    hosts.discard("")
    known = {(urlparse(o.url).hostname, _folder(urlparse(o.url).path)) for o in offenders}

    found: list[str] = []
    for raw in ABSOLUTE.findall(text):
        url = raw.rstrip(".,;:")
        p = urlparse(url)
        if p.hostname in hosts and (p.hostname, _folder(p.path)) not in known:
            found.append(url)
    for path in ROOT_RELATIVE.findall(text):
        if not any((h, _folder(path)) in known for h in hosts):
            found.append(path)
    return list(dict.fromkeys(found))
