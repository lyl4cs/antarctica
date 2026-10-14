import { describe, expect, it } from "vitest";
import {
  METRICS,
  band,
  displayUrl,
  findingScore,
  formatBytes,
  formatClockSeconds,
  formatCost,
  formatDuration,
  formatMetric,
  formatMs,
  formatRelativeDay,
  lowerIsBetterDelta,
  normalizeUrlInput,
  rateMetric,
  scoreDelta,
  sourceLink,
} from "./format";

const def = (key: string) => METRICS.find((m) => m.key === key)!;

describe("number formatting", () => {
  it("shows seconds from 1 s up and milliseconds below", () => {
    expect(formatMs(4820)).toBe("4.8 s");
    expect(formatMs(1000)).toBe("1.0 s");
    expect(formatMs(410.4)).toBe("410 ms");
  });
  it("formats bytes, durations, the timer and cost", () => {
    expect(formatBytes(412000)).toBe("412 KB");
    expect(formatBytes(1_500_000)).toBe("1.5 MB");
    expect(formatBytes(900)).toBe("900 B");
    expect(formatDuration(41_000)).toBe("41 s");
    expect(formatDuration(112_000)).toBe("1 m 52 s");
    expect(formatDuration(120_000)).toBe("2 m");
    expect(formatClockSeconds(41.9)).toBe("0:41");
    expect(formatClockSeconds(125)).toBe("2:05");
    expect(formatCost(0.00421)).toBe("$0.0042");
  });
  it("formats metrics: ms as time, CLS unitless, missing as a dash", () => {
    expect(formatMetric(def("LCP"), 4820)).toBe("4.8 s");
    expect(formatMetric(def("TBT"), 410)).toBe("410 ms");
    expect(formatMetric(def("CLS"), 0.0213)).toBe("0.02");
    expect(formatMetric(def("SI"), null)).toBe("—");
  });
});

describe("ratings", () => {
  it("bands scores like Lighthouse", () => {
    expect(band(90).label).toBe("Good");
    expect(band(89).label).toBe("Needs work");
    expect(band(50).tone).toBe("mid");
    expect(band(49).tone).toBe("poor");
  });
  it("rates metrics against Lighthouse thresholds and places the marker", () => {
    expect(rateMetric(def("LCP"), 2500).label).toBe("Good");
    expect(rateMetric(def("LCP"), 4000).label).toBe("Needs work");
    expect(rateMetric(def("LCP"), 4820).label).toBe("Poor");
    expect(rateMetric(def("CLS"), 0.3).tone).toBe("poor");
    const r = rateMetric(def("TBT"), 450); // bar spans 0..900
    expect(r.marker).toBeCloseTo(50);
    expect(r.widths.good + r.widths.mid + r.widths.poor).toBeCloseTo(100);
    expect(rateMetric(def("TBT"), 99999).marker).toBe(100);
    expect(rateMetric(def("TBT"), null)).toMatchObject({ label: "No data", marker: null });
  });
  it("converts audit scores 0..1 to 0..100", () => {
    expect(findingScore(0.21)).toBe(21);
    expect(findingScore(null)).toBeNull();
  });
});

describe("deltas", () => {
  it("treats lower times as better", () => {
    expect(lowerIsBetterDelta(7350, 4820, formatMs)).toEqual({ label: "− 2.5 s", direction: "better" });
    expect(lowerIsBetterDelta(410, 520, formatMs)).toEqual({ label: "+ 110 ms", direction: "worse" });
    expect(lowerIsBetterDelta(5, 5, String)).toEqual({ label: "± 0", direction: "same" });
    expect(lowerIsBetterDelta(null, 5, String)).toBeNull();
  });
  it("treats higher scores as better", () => {
    expect(scoreDelta(31, 54)).toEqual({ label: "+23", direction: "better" });
    expect(scoreDelta(54, 49)).toEqual({ label: "−5", direction: "worse" });
  });
});

describe("URLs and dates", () => {
  it("normalizes typed URLs", () => {
    expect(normalizeUrlInput("northwind.shop")).toBe("https://northwind.shop/");
    expect(normalizeUrlInput("  http://a.com/x ")).toBe("http://a.com/x");
    expect(normalizeUrlInput("")).toBeNull();
    expect(normalizeUrlInput("not a url")).toBeNull();
    expect(normalizeUrlInput("ftp://a.com")).toBeNull();
    expect(normalizeUrlInput("javascript:alert(1)")).toBeNull();
  });
  it("displays URLs without scheme or trailing slash", () => {
    expect(displayUrl("https://studio-kite.dev/work/")).toBe("studio-kite.dev/work");
  });
  it("only links http(s) sources", () => {
    expect(sourceLink("https://web.dev/articles/optimize-lcp")).toEqual({
      label: "web.dev/articles/optimize-lcp",
      href: "https://web.dev/articles/optimize-lcp",
    });
    expect(sourceLink("web.dev/js")).toEqual({ label: "web.dev/js", href: null });
    expect(sourceLink("javascript:alert(1)").href).toBeNull();
  });
  it("labels today and yesterday", () => {
    const now = new Date(2026, 9, 14, 16, 0);
    expect(formatRelativeDay(new Date(2026, 9, 14, 15, 25), now)).toBe("Today, 3:25 PM");
    expect(formatRelativeDay(new Date(2026, 9, 13, 9, 12), now)).toBe("Yesterday, 9:12 AM");
    expect(formatRelativeDay(new Date(2026, 9, 11, 16, 40), now)).toBe("Oct 11, 4:40 PM");
  });
});
