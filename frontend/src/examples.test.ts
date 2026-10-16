import { describe, expect, it } from "vitest";
import { CASE_STUDY, type CaseStudy, hasCaseStudy } from "./examples";

const full: CaseStudy = {
  url: "https://shop.test/",
  label: "shop.test",
  note: "n",
  steps: [
    { scanId: "a", title: "Baseline", detail: "d" },
    { scanId: "b", title: "After", detail: "d" },
  ],
};

describe("hasCaseStudy", () => {
  it("shows once two scans that really happened are in the story", () => {
    expect(hasCaseStudy(full)).toBe(true);
  });

  it("stays hidden with only one measured step", () => {
    // the state this sits in between scanning a site and actually fixing it
    const one = { ...full, steps: [full.steps[0]] };
    expect(hasCaseStudy(one)).toBe(false);
  });

  it("does not count a pending step as a measured one", () => {
    // A step with no scanId is merged-but-not-deployed work. It is shown, but it
    // is not evidence, so it cannot be what tips the showcase into existence.
    const pending = {
      ...full,
      steps: [full.steps[0], { scanId: "", title: "Planned", detail: "d" }],
    };
    expect(hasCaseStudy(pending)).toBe(false);
  });

  it("stays hidden with no steps or no url", () => {
    expect(hasCaseStudy({ ...full, steps: [] })).toBe(false);
    expect(hasCaseStudy({ ...full, url: "" })).toBe(false);
  });
});

describe("CASE_STUDY", () => {
  it("is filled in and shows", () => {
    expect(hasCaseStudy(CASE_STUDY)).toBe(true);
  });

  it("points at the www host, not the apex", () => {
    // The apex 308-redirects to www, and the scan is penalised for the redirect,
    // so a case study built on the apex would be measuring the redirect.
    expect(CASE_STUDY.url).toBe("https://www.sn0wy.dev/");
  });

  it("stores no scores: they are read from the API at render time", () => {
    // The whole point of the split (see examples.ts). If a score ever gets
    // hardcoded here it can drift from what the database actually says, on the one
    // page whose entire job is to be checkable evidence.
    const text = JSON.stringify(CASE_STUDY);
    expect(text).not.toMatch(/"score"/);
    expect(text).not.toMatch(/\b(88|96)\b/);
  });

  it("keeps the steps in the order they happened", () => {
    const measured = CASE_STUDY.steps.filter((s) => s.scanId);
    expect(measured.length).toBeGreaterThanOrEqual(2);
    // Pending steps come last: work not yet deployed cannot precede work that is.
    const firstPending = CASE_STUDY.steps.findIndex((s) => !s.scanId);
    if (firstPending !== -1) {
      expect(CASE_STUDY.steps.slice(firstPending).every((s) => !s.scanId)).toBe(true);
    }
  });

  it("gives every step a unique scan id", () => {
    const ids = CASE_STUDY.steps.map((s) => s.scanId).filter(Boolean);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
