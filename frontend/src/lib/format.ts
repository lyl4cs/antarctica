/**
 * Formatting and rating helpers shared by every screen.
 *
 * HOW IT WORKS
 * Pure functions only: numbers and dates in, display strings or small objects out.
 * No React here, so each one is unit-tested directly (format.test.ts).
 *
 * WHY THESE RULES
 * - Durations: Lighthouse reports milliseconds. Like the design (and Lighthouse's
 *   own UI) we show seconds once a value reaches 1 s ("4.8 s") and whole
 *   milliseconds below that ("410 ms"), because "0.4 s" hides the precision that
 *   matters for TBT. CLS is a unitless score, shown with 2 decimals.
 * - Bands use Lighthouse's own thresholds: score 90+ good, 50-89 needs work,
 *   below 50 poor. Per-metric thresholds are Lighthouse's "good" / "poor" cut-offs
 *   for mobile, so our labels never disagree with what Lighthouse itself says.
 */

import type { MetricKey } from "../api";

export type Tone = "good" | "mid" | "poor";

export interface Band {
  label: "Good" | "Needs work" | "Poor";
  tone: Tone;
  /** Bar color used by the score tick strip. */
  bar: string;
}

export function band(score: number): Band {
  if (score >= 90) return { label: "Good", tone: "good", bar: "#2F7FB9" };
  if (score >= 50) return { label: "Needs work", tone: "mid", bar: "#D98A2B" };
  return { label: "Poor", tone: "poor", bar: "#C2452D" };
}

/** 4820 -> "4.8 s", 410 -> "410 ms". */
export function formatMs(ms: number): string {
  if (Math.abs(ms) >= 1000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms)} ms`;
}

/** 412000 -> "412 KB", 1_500_000 -> "1.5 MB". Bytes are decimal (like Lighthouse). */
export function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes >= 1000) return `${Math.round(bytes / 1000)} KB`;
  return `${Math.round(bytes)} B`;
}

/** Wall-clock durations: 41_000 -> "41 s", 112_000 -> "1 m 52 s". */
export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  if (total < 60) return `${total} s`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return s ? `${m} m ${s} s` : `${m} m`;
}

/** Elapsed timer: 41 -> "0:41", 125 -> "2:05". */
export function formatClockSeconds(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** "3:24 PM", or "3:24:08 PM" with seconds. Local time zone. */
export function formatTime(d: Date, withSeconds = false): string {
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    ...(withSeconds ? { second: "2-digit" } : {}),
  });
}

/** "Oct 14" */
export function formatShortDate(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** "Aug 19, 2026" */
export function formatLongDate(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  );
}

/** "Today, 3:25 PM" / "Yesterday, 9:12 AM" / "Oct 11, 4:40 PM" */
export function formatRelativeDay(d: Date, now: Date = new Date()): string {
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const day = sameDay(d, now) ? "Today" : sameDay(d, yesterday) ? "Yesterday" : formatShortDate(d);
  return `${day}, ${formatTime(d)}`;
}

/** "https://www.a.com/shop/" -> "www.a.com/shop". What a person would type. */
export function displayUrl(url: string): string {
  return url.replace(/^https?:\/\//i, "").replace(/\/+$/, "");
}

/**
 * Turn what someone typed into a URL the API accepts, or null if hopeless.
 * "northwind.shop" -> "https://northwind.shop". The API validates again (422).
 */
export function normalizeUrlInput(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const u = new URL(withScheme);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    if (!u.hostname.includes(".") && u.hostname !== "localhost") return null;
    return u.toString();
  } catch {
    return null;
  }
}

/** Lighthouse audit score 0..1 -> 0..100 for display. */
export function findingScore(score: number | null): number | null {
  return score === null ? null : Math.round(score * 100);
}

export interface MetricDef {
  field: MetricKey;
  key: string;
  name: string;
  good: number;
  poor: number;
  unitless?: boolean;
  /** Plain-English explanation behind the "?" on reports and the history diff.
   *  Written for someone who has never heard of Core Web Vitals: what the number
   *  describes from the visitor's point of view, then what counts as good. */
  help: string;
}

/** Display order matches the design: LCP, TBT, CLS, FCP, SI. */
export const METRICS: MetricDef[] = [
  {
    field: "lcp_ms", key: "LCP", name: "Largest Contentful Paint", good: 2500, poor: 4000,
    help: "How long until the biggest thing on screen finishes loading, usually your hero " +
      "image or headline. It's the closest single number to \u201cwhen did the page feel " +
      "ready\u201d. Under 2.5s is good, over 4s is poor.",
  },
  {
    field: "tbt_ms", key: "TBT", name: "Total Blocking Time", good: 200, poor: 600,
    help: "How long the page was frozen and ignoring taps while JavaScript ran. High TBT is " +
      "why a page looks finished but nothing happens when you tap it. Under 200ms is good, " +
      "over 600ms is poor.",
  },
  {
    field: "cls", key: "CLS", name: "Cumulative Layout Shift", good: 0.1, poor: 0.25,
    unitless: true,
    help: "How much the page jumps around while it loads, the thing that makes you tap the " +
      "wrong button. It's a score, not a time. Under 0.1 is good, over 0.25 is poor.",
  },
  {
    field: "fcp_ms", key: "FCP", name: "First Contentful Paint", good: 1800, poor: 3000,
    help: "How long until anything at all appears instead of a blank screen. It doesn't mean " +
      "the page is usable yet, just that something showed up. Under 1.8s is good, over 3s " +
      "is poor.",
  },
  {
    field: "speed_index_ms", key: "SI", name: "Speed Index", good: 3400, poor: 5800,
    help: "How quickly the page fills in visually, rather than one single moment. A page that " +
      "paints in stages scores worse than one that arrives at once. Under 3.4s is good, " +
      "over 5.8s is poor.",
  },
];

export function formatMetric(def: MetricDef, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return def.unitless ? value.toFixed(2) : formatMs(value);
}

export interface MetricRating {
  label: Band["label"] | "No data";
  tone: Tone | "none";
  /** Widths (percent of the bar) of the good / needs-work / poor zones, and the marker. */
  widths: { good: number; mid: number; poor: number };
  marker: number | null;
}

/** Rate a metric and lay out its threshold bar (bar spans 0 .. 1.5 x the poor cut-off). */
export function rateMetric(def: MetricDef, value: number | null | undefined): MetricRating {
  const max = def.poor * 1.5;
  const widths = {
    good: (def.good / max) * 100,
    mid: ((def.poor - def.good) / max) * 100,
    poor: ((max - def.poor) / max) * 100,
  };
  if (value === null || value === undefined) {
    return { label: "No data", tone: "none", widths, marker: null };
  }
  const label = value <= def.good ? "Good" : value <= def.poor ? "Needs work" : "Poor";
  const tone: Tone = label === "Good" ? "good" : label === "Poor" ? "poor" : "mid";
  return { label, tone, widths, marker: Math.min(Math.max(value / max, 0), 1) * 100 };
}

export interface Delta {
  /** "− 1.2 s", "+ 3", "± 0 ms" */
  label: string;
  /** "better" is blue, "worse" is red, "same" is sand. */
  direction: "better" | "worse" | "same";
}

const sign = (d: number) => (d > 0 ? "+" : d < 0 ? "−" : "±");

/**
 * Before -> after change where LOWER is better (times, CLS, finding count).
 * Returns null when either side is missing.
 */
export function lowerIsBetterDelta(
  before: number | null | undefined,
  after: number | null | undefined,
  fmt: (v: number) => string,
): Delta | null {
  if (before === null || before === undefined || after === null || after === undefined) return null;
  const d = after - before;
  const same = Math.abs(d) < 1e-9;
  return {
    label: `${sign(d)} ${fmt(Math.abs(d))}`,
    direction: same ? "same" : d < 0 ? "better" : "worse",
  };
}

/** Score change, where HIGHER is better: 31 -> 54 gives "+23". */
export function scoreDelta(before: number, after: number): Delta {
  const d = after - before;
  return { label: `${sign(d)}${Math.abs(d)}`, direction: d > 0 ? "better" : d < 0 ? "worse" : "same" };
}

/**
 * An AI fix's source, which is either a URL or a doc label like "web.dev/js".
 * We only ever link http(s) URLs; anything else renders as plain text, so a
 * strange value can't become a javascript: link.
 */
export function sourceLink(source: string): { label: string; href: string | null } {
  const s = source.trim();
  if (/^https?:\/\//i.test(s)) {
    try {
      const u = new URL(s);
      return { label: displayUrl(u.host + u.pathname), href: u.toString() };
    } catch {
      return { label: s, href: null };
    }
  }
  return { label: s, href: null };
}

/** "$0.0042" — fix costs are fractions of a cent, so 4 decimals. */
export function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}
