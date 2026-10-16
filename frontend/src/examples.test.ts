import { describe, expect, it } from "vitest";
import { CASE_STUDY, type CaseStudy, hasCaseStudy } from "./examples";

const full: CaseStudy = {
  url: "https://shop.test/",
  label: "shop.test",
  beforeScanId: "a",
  afterScanId: "b",
  note: "n",
};

describe("hasCaseStudy", () => {
  it("shows only when both ends of the before/after exist", () => {
    expect(hasCaseStudy(full)).toBe(true);
  });

  it("stays hidden while the after scan hasn't happened yet", () => {
    // the state this sits in between scanning a site and actually fixing it
    expect(hasCaseStudy({ ...full, afterScanId: "" })).toBe(false);
  });

  it("stays hidden with no before scan or no url", () => {
    expect(hasCaseStudy({ ...full, beforeScanId: "" })).toBe(false);
    expect(hasCaseStudy({ ...full, url: "" })).toBe(false);
  });

  it("is empty today, so nothing half-finished is on the live site", () => {
    // delete this test when CASE_STUDY is filled in for real
    expect(hasCaseStudy(CASE_STUDY)).toBe(false);
  });
});
