/** Renders Lighthouse's inline Markdown safely (see lib/markdown.ts for why). */
import { parseInline } from "../lib/markdown";

export function Inline({ text }: { text: string }) {
  return (
    <>
      {parseInline(text).map((seg, i) => {
        if (seg.kind === "link")
          return (
            <a key={i} href={seg.href} target="_blank" rel="noopener noreferrer">
              {seg.text}
            </a>
          );
        if (seg.kind === "code") return <code key={i}>{seg.text}</code>;
        return <span key={i}>{seg.text}</span>;
      })}
    </>
  );
}
