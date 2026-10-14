/**
 * Geometry for the History page's score chart and scan timeline.
 *
 * HOW IT WORKS
 * Both the line chart and the clickable timeline below it share one horizontal axis
 * made of N equal columns (at least 57, like the design). Each scan gets a column
 * from its timestamp: oldest scan in column 0, newest in column N-1, the rest placed
 * proportionally in time. Then everything is plain arithmetic into the chart's
 * 1000 x 300 SVG viewBox, which the browser scales to any width.
 *
 * WHY COLUMNS INSTEAD OF RAW TIME
 * Real histories bunch up: you scan, fix something, and rescan five minutes later.
 * With pure time positions those two scans would sit on the same pixel and you could
 * not click either one. `assignColumns` keeps time order and proportions but nudges
 * scans apart so each owns at least one column (and so one clickable bar).
 *
 * WHY A HAND-ROLLED SVG
 * It's one line, some dots and a few labels. A chart library would add weight and
 * fight the design; this is ~100 lines and fully tested (chart.test.ts).
 */

import type { ScanSummary } from "../api";

export const MIN_COLUMNS = 57;

// Chart viewBox layout (same numbers as the design's SVG).
export const CHART = { left: 60, right: 960, baseline: 250, width: 1000, height: 300 };

export function xForColumn(col: number, columns: number): number {
  return CHART.left + (columns <= 1 ? 0.5 : col / (columns - 1)) * (CHART.right - CHART.left);
}

/** Score 0..100 -> y; 0 sits on the baseline (y=250), 100 at y=50. */
export function yForScore(score: number): number {
  return CHART.baseline - score * 2;
}

/**
 * Map ascending timestamps to distinct columns in [0, columns-1], proportional to
 * time but at least one column apart. Requires columns >= times.length.
 */
export function assignColumns(times: number[], columns: number): number[] {
  const n = times.length;
  if (n === 0) return [];
  if (n === 1) return [Math.floor((columns - 1) / 2)];
  const t0 = times[0];
  const span = times[n - 1] - t0;
  const ideal = times.map((t, i) =>
    Math.round((span > 0 ? (t - t0) / span : i / (n - 1)) * (columns - 1)),
  );
  const cols = [...ideal];
  for (let i = 1; i < n; i++) cols[i] = Math.max(cols[i], cols[i - 1] + 1); // push right
  cols[n - 1] = Math.min(cols[n - 1], columns - 1);
  for (let i = n - 2; i >= 0; i--) cols[i] = Math.min(cols[i], cols[i + 1] - 1); // pull back
  return cols;
}

export interface PlacedScan {
  summary: ScanSummary;
  col: number;
  x: number;
  /** Only for done scans with a score. */
  y: number | null;
  time: Date;
}

export interface AxisLabel {
  x: number;
  col: number;
  text: string;
  anchor: "start" | "middle" | "end";
}

export interface ChartModel {
  columns: number;
  /** Oldest first. */
  placed: PlacedScan[];
  linePath: string;
  areaPath: string;
  dotsPath: string;
  failPath: string;
  failMarks: number[];
  labels: AxisLabel[];
}

const fmt = (n: number) => n.toFixed(1);

function monthLabel(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Build every path and label for the chart from a newest-first history list. */
export function buildChart(historyNewestFirst: ScanSummary[]): ChartModel {
  const oldestFirst = [...historyNewestFirst].sort(
    (a, b) => Date.parse(a.scan.created_at) - Date.parse(b.scan.created_at),
  );
  const columns = Math.max(MIN_COLUMNS, oldestFirst.length);
  const times = oldestFirst.map((s) => Date.parse(s.scan.created_at));
  const cols = assignColumns(times, columns);

  const placed: PlacedScan[] = oldestFirst.map((summary, i) => {
    const scored = summary.scan.status === "done" && summary.performance_score !== null;
    return {
      summary,
      col: cols[i],
      x: xForColumn(cols[i], columns),
      y: scored ? yForScore(summary.performance_score as number) : null,
      time: new Date(times[i]),
    };
  });

  const scored = placed.filter((p) => p.y !== null) as (PlacedScan & { y: number })[];
  const linePath = scored.map((p, i) => `${i ? "L" : "M"}${fmt(p.x)} ${fmt(p.y)}`).join(" ");
  const areaPath =
    scored.length > 1
      ? `${linePath} L${fmt(scored[scored.length - 1].x)} ${CHART.baseline} L${fmt(scored[0].x)} ${CHART.baseline} Z`
      : "";
  const dotsPath = scored
    .map((p) => `M${fmt(p.x - 4)} ${fmt(p.y)} a4 4 0 1 0 8 0 a4 4 0 1 0 -8 0`)
    .join(" ");

  const failMarks = placed.filter((p) => p.summary.scan.status === "failed").map((p) => p.x);
  const failPath = failMarks
    .map((x) => `M${fmt(x - 5)} 245 L${fmt(x + 5)} 255 M${fmt(x + 5)} 245 L${fmt(x - 5)} 255`)
    .join(" ");

  return { columns, placed, linePath, areaPath, dotsPath, failPath, failMarks, labels: axisLabels(placed, columns) };
}

/** First date, last date, and the 1st of each month in between when there's room. */
export function axisLabels(placed: PlacedScan[], columns: number): AxisLabel[] {
  if (placed.length === 0) return [];
  const first = placed[0];
  const last = placed[placed.length - 1];
  const labels: AxisLabel[] = [
    { x: first.x, col: first.col, text: monthLabel(first.time), anchor: placed.length === 1 ? "middle" : "start" },
  ];
  if (placed.length === 1) return labels;

  const t0 = first.time.getTime();
  const span = last.time.getTime() - t0;
  const GAP = 7; // columns; a label is ~6 columns wide at the design's size
  if (span > 0) {
    const d = new Date(first.time.getFullYear(), first.time.getMonth() + 1, 1);
    while (d.getTime() < last.time.getTime()) {
      const col = Math.round(((d.getTime() - t0) / span) * (columns - 1));
      const prev = labels[labels.length - 1].col;
      if (col - prev >= GAP && last.col - col >= GAP) {
        labels.push({ x: xForColumn(col, columns), col, text: monthLabel(d), anchor: "middle" });
      }
      d.setMonth(d.getMonth() + 1);
    }
  }
  const lastText = monthLabel(last.time);
  if (lastText !== labels[0].text || labels.length > 1) {
    labels.push({ x: last.x, col: last.col, text: lastText, anchor: "end" });
  }
  return labels;
}

/** Keep "Before · 31" labels inside the chart near the edges. */
export function labelAnchor(x: number): "start" | "middle" | "end" {
  return x < 140 ? "start" : x > 880 ? "end" : "middle";
}
