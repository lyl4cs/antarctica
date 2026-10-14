"""Split documents into retrievable chunks.

HOW IT WORKS
Performance docs are markdown. We split on headings first (a heading usually
starts a self-contained idea, e.g. "Defer non-critical CSS"), then cap each chunk
at ~max_words with a small overlap so a sentence cut at a boundary still appears
whole in one of the two chunks.

WHY THESE NUMBERS
- ~300 words is roughly 400 tokens: big enough to hold one complete fix
  explanation, small enough that the top-5 chunks fit comfortably in a prompt.
- 40-word overlap protects against cutting an instruction in half.
Tune both with the eval, don't guess (that's the point of having one).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DocChunk:
    source: str  # URL or file the chunk came from
    heading: str
    text: str


def split_sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in markdown.splitlines():
        if re.match(r"^#{1,4}\s", line):
            if buf and "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = line.lstrip("#").strip(), []
        else:
            buf.append(line)
    if buf and "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))
    return sections


def chunk_markdown(
    markdown: str, source: str, max_words: int = 300, overlap: int = 40
) -> list[DocChunk]:
    chunks: list[DocChunk] = []
    for heading, body in split_sections(markdown):
        words = body.split()
        start = 0
        while start < len(words):
            piece = words[start:start + max_words]
            text = (f"{heading}\n" if heading else "") + " ".join(piece)
            chunks.append(DocChunk(source=source, heading=heading, text=text))
            if start + max_words >= len(words):
                break
            start += max_words - overlap
    return chunks
