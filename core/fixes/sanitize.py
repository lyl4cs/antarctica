"""Keep text copied off a scanned website from acting like part of the prompt.

THE EXPOSURE
sn0wy scans URLs anyone submits, and parts of what it finds there end up in the
Gemini prompt: the page's own URL and the URLs of the resources an audit blames.
Those strings come from a site we do not control, so they are attacker-supplied
input that reaches a model whose output a human is invited to copy and paste.

The attack that matters is not someone jailbreaking their own scan. It is this:
host a page, scan it, send the report link to someone else, and have the fix
suggestion they copy contain something you chose. `code` is rendered with a copy
button, so the last step is one click.

WHAT THIS DOES
Two cheap, boring things that remove most of the surface:

1. Flatten to one line. The prompt is a structured document built out of lines
   and labelled blocks. A newline inside a URL lets the text below it pose as a
   new section, which is how "- https://a.test/x" becomes a forged instruction.
   Collapsing every run of whitespace, and dropping control characters outright,
   means a value can never be more than the one field it was put in.

2. Bound the length. A multi-kilobyte URL is not a resource reference, it is a
   payload with somewhere to hide. Truncation is visible, so a fix written from a
   cut URL reads as obviously wrong rather than quietly wrong.

WHAT THIS DOES NOT DO
It does not try to detect instruction-like text. Pattern-matching for "ignore
previous instructions" is a losing game and gives false confidence. The prompt
instead labels this content as untrusted data (see suggest.PROMPT), which is a
statement the model can act on, and `verify.unverified_urls` already flags output
that names site URLs the audit never saw.

Normal URLs pass through byte for byte. Anything this changes was already not a
URL.
"""

from __future__ import annotations

import re

#: Longest URL that still reads as a resource reference rather than a payload.
MAX_URL = 300

#: Any whitespace run, including the newlines and tabs that could fake prompt
#: structure. Control characters are removed separately, not turned into spaces.
_WHITESPACE = re.compile(r"\s+")

#: C0/C1 controls and the zero-width characters that hide text inside a line.
_CONTROL = re.compile(
    "["
    "\\x00-\\x1f\\x7f-\\x9f"          # C0 and C1 control characters
    "\\u200b-\\u200f"                # zero-width and bidi marks
    "\\u2028\\u2029\\ufeff"            # line/paragraph separators, BOM
    "]"
)

#: Marks a value the prompt shows in truncated form.
TRUNCATED = "…[truncated]"


def one_line(text: str, limit: int = MAX_URL) -> str:
    """`text` as a single bounded line, safe to drop into a prompt field.

    Removes control and zero-width characters, collapses whitespace runs to one
    space, trims, and truncates past `limit` with a visible marker. A normal URL
    is returned unchanged.
    """
    cleaned = _CONTROL.sub("", text)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - len(TRUNCATED)] + TRUNCATED
