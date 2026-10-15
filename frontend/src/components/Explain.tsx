/**
 * A "?" that explains a term in plain English.
 *
 * WHY A BUTTON AND NOT A title= TOOLTIP
 * `title` never appears on touch, takes a second to show on hover, and isn't
 * reachable by keyboard. The people this is for (someone running a Shopify store
 * who has never heard of Total Blocking Time) are often on a phone.
 *
 * So: a real button that toggles. Click or tap opens it, Escape and clicking
 * elsewhere close it, and the panel is tied to the button with aria-describedby
 * so a screen reader announces it.
 */
import { useEffect, useId, useRef, useState } from "react";

export function Explain({ label, children }: { label: string; children: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrap = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  return (
    <span className="explain" ref={wrap}>
      <button
        type="button"
        className="explain-btn"
        aria-label={`What is ${label}?`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open && (
        <span className="explain-pop" id={id} role="note">
          <strong>{label}</strong>
          {children}
        </span>
      )}
    </span>
  );
}
