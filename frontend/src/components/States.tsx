/**
 * Loading, error and empty states, so every fetch on every page looks and reads
 * the same. Errors use role="alert" so screen readers announce them; loading uses
 * role="status" (polite).
 */
import type { ReactNode } from "react";
import { SpinnerIcon } from "./Icons";

export function Loading({ label }: { label: string }) {
  return (
    <p className="loading-line" role="status">
      <SpinnerIcon size={18} />
      {label}
    </p>
  );
}

export function ErrorState({
  title,
  message,
  children,
}: {
  title: string;
  message: string;
  children?: ReactNode;
}) {
  return (
    <div className="state state-error" role="alert">
      <span className="eyebrow">Error</span>
      <h2>{title}</h2>
      <p>{message}</p>
      {children}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state state-center">
      <h2>{title}</h2>
      {children}
    </div>
  );
}
