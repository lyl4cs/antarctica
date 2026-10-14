/**
 * Pure view-model for the scan-in-progress screen: which step is current, what the
 * heading says, and how tall each bar of the elapsed-time strip is.
 *
 * Kept out of the component so the rules are readable in one place and testable
 * without rendering. The numbers (31 bars for 0-60 s, gaussian bump around "now")
 * come straight from the design's renderVals().
 */
import type { Mood } from "../components/Illustrations";

export type Phase = "queued" | "running" | "ready";

export interface StepView {
  label: string;
  state: "done" | "current" | "todo";
  /** Line after the dot is dark once that step is passed. */
  passed: boolean;
}

export function steps(phase: Phase): StepView[] {
  const order: Phase[] = ["queued", "running", "ready"];
  const idx = order.indexOf(phase);
  return ["Queued", "Running", "Report ready"].map((label, i) => {
    const done = i < idx || (phase === "ready" && i === 2);
    const current = i === idx && phase !== "ready";
    return { label, state: done ? "done" : current ? "current" : "todo", passed: i < idx };
  });
}

export function mood(phase: Phase): Mood {
  return phase === "queued" ? "sleep" : phase === "running" ? "awake" : "happy";
}

export interface TickView {
  h: number;
  c: string;
}

/** One bar per 2 s from 0 to 60 s. Past bars are blue, the bars around "now" grow. */
export function ticks(phase: Phase, elapsedSeconds: number): TickView[] {
  const out: TickView[] = [];
  for (let v = 0; v <= 60; v += 2) {
    const passed = v <= elapsedSeconds && phase !== "queued";
    const near = phase === "running" ? Math.exp(-((v - elapsedSeconds) ** 2) / (2 * 16)) : 0;
    const h = Math.round(12 + (passed ? 10 : 0) + 30 * near);
    out.push({ h, c: passed ? (near > 0.6 ? "#12202B" : "#2F7FB9") : "#D6CFC0" });
  }
  return out;
}
