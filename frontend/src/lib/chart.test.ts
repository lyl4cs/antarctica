import { describe, expect, it } from "vitest";
import type { ScanSummary } from "../api";
import { CHART, MIN_COLUMNS, assignColumns, buildChart, xForColumn, yForScore } from "./chart";

function summary(id: string, iso: string, status: string, score: number | null): ScanSummary {
  return {
    scan: { id, url: "https://a.com/", status: status as never, attempts: 1, error: null, duration_ms: 1, created_at: iso, finished_at: iso },
    performance_score: score,
  };
}

describe("assignColumns", () => {
  it("places scans proportionally in time", () => {
    expect(assignColumns([0, 50, 100], 11)).toEqual([0, 5, 10]);
  });
  it("gives bunched-up scans their own column, keeping order and the ends", () => {
    const cols = assignColumns([0, 1, 2, 1000], 57);
    expect(cols).toEqual([0, 1, 2, 56]);
    const tail = assignColumns([0, 998, 999, 1000], 57);
    expect(tail).toEqual([0, 54, 55, 56]);
  });
  it("spreads identical timestamps evenly", () => {
    expect(assignColumns([5, 5, 5], 5)).toEqual([0, 2, 4]);
  });
  it("centers a single scan", () => {
    expect(assignColumns([5], 57)).toEqual([28]);
  });
});

describe("buildChart", () => {
  const history = [
    summary("c", "2026-10-14T15:24:00Z", "done", 54),
    summary("f", "2026-09-27T09:15:00Z", "failed", null),
    summary("b", "2026-09-01T12:00:00Z", "done", 40),
    summary("a", "2026-08-19T15:03:00Z", "done", 31),
  ];
  const m = buildChart(history);

  it("orders oldest first across at least 57 columns", () => {
    expect(m.columns).toBe(MIN_COLUMNS);
    expect(m.placed.map((p) => p.summary.scan.id)).toEqual(["a", "b", "f", "c"]);
    expect(m.placed[0].x).toBe(CHART.left);
    expect(m.placed[3].x).toBe(CHART.right);
  });
  it("draws the line through scored scans only and marks failures", () => {
    expect(m.linePath.startsWith(`M60.0 ${yForScore(31).toFixed(1)}`)).toBe(true);
    expect(m.linePath.match(/[ML]/g)).toHaveLength(3);
    expect(m.failMarks).toHaveLength(1);
    expect(m.areaPath.endsWith("Z")).toBe(true);
  });
  it("labels the ends and month starts with room", () => {
    expect(m.labels.map((l) => l.text)).toEqual(["Aug 19", "Sep 1", "Oct 1", "Oct 14"]);
    expect(m.labels[0].anchor).toBe("start");
    expect(m.labels[m.labels.length - 1].anchor).toBe("end");
  });
  it("handles empty and single histories", () => {
    expect(buildChart([]).linePath).toBe("");
    const one = buildChart([summary("a", "2026-10-14T15:24:00Z", "done", 54)]);
    expect(one.placed[0].x).toBeCloseTo(xForColumn(28, 57));
    expect(one.areaPath).toBe("");
    expect(one.labels).toHaveLength(1);
  });
});
