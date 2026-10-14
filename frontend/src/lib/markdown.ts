/**
 * Tiny parser for the inline Markdown inside Lighthouse audit descriptions.
 *
 * HOW IT WORKS
 * Lighthouse writes descriptions like
 *   "Serve images that are appropriately-sized ... [Learn more](https://...)."
 * and sometimes `code` spans. `parseInline` splits such a string into a flat list
 * of segments: plain text, links, and code. The React side (components/Inline.tsx)
 * renders each segment as a text node, <a> or <code>.
 *
 * WHY NOT dangerouslySetInnerHTML OR A MARKDOWN LIBRARY
 * The text comes from scanning arbitrary websites, so it is untrusted. Building
 * React elements from segments means nothing in it is ever parsed as HTML, and only
 * http(s) links become real links. Two regexes are all Lighthouse needs; a full
 * Markdown library would be ~30 KB for this.
 */

export type Segment =
  | { kind: "text"; text: string }
  | { kind: "code"; text: string }
  | { kind: "link"; text: string; href: string };

const TOKEN = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|`([^`]+)`/g;

export function parseInline(input: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of input.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ kind: "text", text: input.slice(last, at) });
    if (m[1] !== undefined && m[2] !== undefined) out.push({ kind: "link", text: m[1], href: m[2] });
    else if (m[3] !== undefined) out.push({ kind: "code", text: m[3] });
    last = at + m[0].length;
  }
  if (last < input.length) out.push({ kind: "text", text: input.slice(last) });
  return out;
}
