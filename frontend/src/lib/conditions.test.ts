import { describe, expect, it } from "vitest";
import type { Conditions } from "../api";
import { comparabilityProblems, describeConditions, hostSpeedGap } from "./conditions";

const mobile: Conditions = {
  lighthouse_version: "12.8.2",
  form_factor: "mobile",
  throttling_method: "simulate",
  cpu_slowdown: 4,
  rtt_ms: 150,
  throughput_kbps: 1638.4,
  benchmark_index: 1250,
};

describe("describeConditions", () => {
  it("summarises the default throttled mobile run", () => {
    expect(describeConditions(mobile)).toBe(
      "Mobile · slow 4G (1638 Kbps) · 4x CPU slowdown · Lighthouse 12.8.2",
    );
  });

  it("says so when nothing was throttled", () => {
    const desktop = { ...mobile, form_factor: "desktop", throttling_method: "provided", cpu_slowdown: 1 };
    expect(describeConditions(desktop)).toBe("Desktop · no throttling · Lighthouse 12.8.2");
  });

  it("returns null when the scan predates conditions, so the UI renders nothing", () => {
    expect(describeConditions(undefined)).toBeNull();
    expect(describeConditions({})).toBeNull();
  });
});

describe("comparabilityProblems", () => {
  it("passes identical settings", () => {
    expect(comparabilityProblems(mobile, { ...mobile })).toEqual([]);
  });

  it("allows different patch versions within one major", () => {
    // scoring weights are stable inside a major, so 12.2.1 vs 12.8.2 is fine
    expect(comparabilityProblems(mobile, { ...mobile, lighthouse_version: "12.2.1" })).toEqual([]);
  });

  it("catches a major version change", () => {
    const [problem] = comparabilityProblems(mobile, { ...mobile, lighthouse_version: "13.0.0" });
    expect(problem).toContain("different Lighthouse majors");
  });

  it("catches mobile vs desktop", () => {
    const [problem] = comparabilityProblems(mobile, { ...mobile, form_factor: "desktop" });
    expect(problem).toBe("one ran as mobile, the other as desktop");
  });

  it("catches throttling changes", () => {
    expect(comparabilityProblems(mobile, { ...mobile, cpu_slowdown: 1 })).toContain(
      "different CPU slowdown (4x and 1x)",
    );
    expect(comparabilityProblems(mobile, { ...mobile, throttling_method: "provided" })).toContain(
      "different throttling (simulate and provided)",
    );
  });

  it("reports every mismatch, not just the first", () => {
    const other = { ...mobile, form_factor: "desktop", cpu_slowdown: 1, lighthouse_version: "13.0.0" };
    expect(comparabilityProblems(mobile, other)).toHaveLength(3);
  });

  it("does not invent a mismatch when one side is unknown", () => {
    // an old scan has no conditions: we can't claim a difference we can't see
    expect(comparabilityProblems(mobile, {})).toEqual([]);
    expect(comparabilityProblems(mobile, undefined)).toEqual([]);
  });

  it("ignores host speed, which differs on nearly every run", () => {
    expect(comparabilityProblems(mobile, { ...mobile, benchmark_index: 600 })).toEqual([]);
  });
});

describe("hostSpeedGap", () => {
  it("stays quiet about normal variation", () => {
    expect(hostSpeedGap(mobile, { ...mobile, benchmark_index: 1200 })).toBeNull();
  });

  it("flags a big difference between the machines", () => {
    expect(hostSpeedGap(mobile, { ...mobile, benchmark_index: 625 })).toBe(50);
  });

  it("is null when either side is unknown", () => {
    expect(hostSpeedGap(mobile, {})).toBeNull();
  });
});
