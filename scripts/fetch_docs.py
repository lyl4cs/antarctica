"""Download web performance articles and save them as markdown-ish text.

Run on YOUR machine (needs internet):  python scripts/fetch_docs.py
Output: data/docs/<slug>.md, each starting with "Source: <url>".
Then embed them:  python scripts/ingest_docs.py
"""

from __future__ import annotations

import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URLS = Path(__file__).parent / "doc_urls.txt"
OUT = Path("data/docs")


class _TextExtractor(HTMLParser):
    """Keeps headings and paragraph-ish text from <main>/<article>; drops nav, scripts."""

    SKIP = {"script", "style", "nav", "header", "footer", "aside", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in {"h1", "h2", "h3", "h4"} and not self._skip:
            self.parts.append("\n" + "#" * int(tag[1]) + " ")
        elif tag in {"p", "li", "pre", "br"} and not self._skip:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def slugify(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.lower().split("//", 1)[-1]).strip("-")[:80]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    urls = [u.strip() for u in URLS.read_text().splitlines() if u.strip() and not u.startswith("#")]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "antarctica-docs/0.1"})
            html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            print(f"skip {url}: {e}", file=sys.stderr)
            continue
        (OUT / f"{slugify(url)}.md").write_text(f"Source: {url}\n\n{html_to_text(html)}")
        print(f"saved {url}")


if __name__ == "__main__":
    main()
