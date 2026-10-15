/**
 * Measurement conditions: how a score was produced, and whether two scores can
 * honestly be compared.
 *
 * WHY THIS EXISTS
 * A Lighthouse score has no meaning on its own. The default run emulates a
 * mid-range phone on a throttled connection with the CPU slowed 4x; the same page
 * measured as "desktop, no throttling" scores far higher without changing at all.
 * Major Lighthouse versions also reweight the metrics.
 *
 * So the history chart and the before/after diff can show a 12-point "improvement"
 * that is purely a config difference. Rather than letting the UI state that as
 * fact, `comparabilityProblems` returns the reasons two scans aren't comparable,
 * and the diff says so instead of pretending.
 *
 * `benchmark_index` is deliberately NOT a comparability check: it varies between
 * runs on the same settings (different Cloud Run hardware), so blocking on it
 * would block almost every comparison. It's shown as context for small swings.
 */
import type { Conditions } from "../api";

/** "mobile, slow 4G, 4x CPU, Lighthouse 12.8.2" - the one-line summary by the score. */
export function describeConditions(c: Conditions | undefined): string | null {
  if (!c) return null;
  const parts: string[] = [];
  if (c.form_factor) parts.push(c.form_factor === "mobile" ? "Mobile" : "Desktop");

  if (c.throttling_method === "provided") {
    parts.push("no throttling");
  } else if (c.throughput_kbps) {
    parts.push(`${describeNetwork(c.throughput_kbps)} (${Math.round(c.throughput_kbps)} Kbps)`);
  }
  if (c.cpu_slowdown && c.cpu_slowdown > 1) parts.push(`${c.cpu_slowdown}x CPU slowdown`);
  if (c.lighthouse_version) parts.push(`Lighthouse ${c.lighthouse_version}`);

  return parts.length ? parts.join(" · ") : null;
}

/** Lighthouse's own simulated presets, named the way its docs do. */
function describeNetwork(kbps: number): string {
  if (kbps <= 400) return "slow 3G";
  if (kbps <= 1700) return "slow 4G";
  if (kbps <= 11000) return "fast 4G";
  return "fast connection";
}

/** Major version only: weights are stable within a major, so 12.2 vs 12.8 is fine. */
function major(version: string | null | undefined): string | null {
  return version ? (version.split(".")[0] ?? null) : null;
}

/**
 * Why these two scans can't be compared, in plain words. Empty means they can.
 * Unknown on either side is not a mismatch: we can't claim a difference we can't see.
 */
export function comparabilityProblems(a: Conditions | undefined, b: Conditions | undefined): string[] {
  if (!a || !b) return [];
  const problems: string[] = [];
  const differs = <T,>(x: T | null | undefined, y: T | null | undefined) =>
    x != null && y != null && x !== y;

  if (differs(a.form_factor, b.form_factor)) {
    problems.push(`one ran as ${a.form_factor}, the other as ${b.form_factor}`);
  }
  if (differs(major(a.lighthouse_version), major(b.lighthouse_version))) {
    problems.push(
      `different Lighthouse majors (${a.lighthouse_version} and ${b.lighthouse_version}), which score differently`,
    );
  }
  if (differs(a.throttling_method, b.throttling_method)) {
    problems.push(`different throttling (${a.throttling_method} and ${b.throttling_method})`);
  }
  if (differs(a.cpu_slowdown, b.cpu_slowdown)) {
    problems.push(`different CPU slowdown (${a.cpu_slowdown}x and ${b.cpu_slowdown}x)`);
  }
  if (differs(a.throughput_kbps, b.throughput_kbps)) {
    problems.push("different simulated network speeds");
  }
  return problems;
}

/**
 * How far apart the two host machines were, as a percentage, or null when that's
 * not worth mentioning. Throttling is relative to the host, so a slower worker
 * drags the simulated phone down with it.
 */
export function hostSpeedGap(a: Conditions | undefined, b: Conditions | undefined): number | null {
  const x = a?.benchmark_index;
  const y = b?.benchmark_index;
  if (!x || !y) return null;
  const gap = Math.round((Math.abs(x - y) / Math.max(x, y)) * 100);
  return gap >= 15 ? gap : null;
}
