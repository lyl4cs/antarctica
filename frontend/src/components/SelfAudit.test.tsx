/**
 * The showcase's job is to be checkable evidence, so these tests are mostly about
 * what it must NOT do: invent a score, keep asserting one after the scan behind it
 * is gone, or let unshipped work read as a measured result.
 */
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { ScanSummary } from "../api";
import { CASE_STUDY } from "../examples";
import { scoreDelta } from "../lib/format";
import { SelfAudit, resolveSteps } from "./SelfAudit";

// Derived, not hardcoded: scoreDelta renders a real minus sign (U+2212), not a
// hyphen, and a test that spells it out by hand drifts the moment that changes.
const DELTA_RE = /^[+−±]\d/;

function summary(id: string, score: number | null, created = "2026-10-16T02:28:11Z"): ScanSummary {
  return {
    scan: {
      id,
      url: CASE_STUDY.url,
      status: "done",
      attempts: 1,
      error: null,
      duration_ms: 1000,
      created_at: created,
      finished_at: created,
    },
    performance_score: score,
  };
}

/** The real steps, with scores supplied the way the API would supply them. */
function historyFor(scores: number[]): ScanSummary[] {
  const measured = CASE_STUDY.steps.filter((s) => s.scanId);
  return measured.map((s, i) => summary(s.scanId, scores[i] ?? null));
}

function renderAudit(history: ScanSummary[]) {
  return render(
    <MemoryRouter>
      <SelfAudit history={history} />
    </MemoryRouter>,
  );
}

describe("resolveSteps", () => {
  it("takes each score from the history, never from the step", () => {
    const steps = [{ scanId: "a", title: "t", detail: "d" }];
    expect(resolveSteps(steps, [summary("a", 73)])[0].score).toBe(73);
  });

  it("reports an unknown score when the scan is not in the history", () => {
    // A deleted or re-pointed scan must not leave a stale number on the page.
    const steps = [{ scanId: "gone", title: "t", detail: "d" }];
    const [r] = resolveSteps(steps, [summary("a", 73)]);
    expect(r.score).toBeNull();
    expect(r.summary).toBeNull();
  });

  it("treats a step with no scanId as unmeasured", () => {
    const [r] = resolveSteps([{ scanId: "", title: "t", detail: "d" }], []);
    expect(r.score).toBeNull();
    expect(r.summary).toBeNull();
  });
});

describe("SelfAudit", () => {
  it("renders every step, measured and pending", () => {
    renderAudit(historyFor([88, 96]));
    for (const step of CASE_STUDY.steps) {
      expect(screen.getByRole("heading", { name: step.title })).toBeInTheDocument();
    }
  });

  it("shows the scores the history reports", () => {
    renderAudit(historyFor([88, 96]));
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("96")).toBeInTheDocument();
  });

  it("shows a different score when the history says something different", () => {
    // Guards the actual contract: the numbers are not baked into the component.
    renderAudit(historyFor([41, 59]));
    expect(screen.getByText("41")).toBeInTheDocument();
    expect(screen.getByText("59")).toBeInTheDocument();
    expect(screen.queryByText("88")).not.toBeInTheDocument();
  });

  it("labels the gain between consecutive measured steps", () => {
    renderAudit(historyFor([88, 96]));
    expect(screen.getByText(scoreDelta(88, 96).label)).toBeInTheDocument();
  });

  it("labels a regression as a regression", () => {
    renderAudit(historyFor([96, 88]));
    expect(screen.getByText(scoreDelta(96, 88).label)).toBeInTheDocument();
  });

  it("gives the first step no delta, having nothing to compare against", () => {
    renderAudit(historyFor([88, 96]));
    const first = screen.getByRole("heading", { name: CASE_STUDY.steps[0].title })
      .closest("li") as HTMLElement;
    expect(within(first).queryByText(DELTA_RE)).not.toBeInTheDocument();
  });

  it("renders no score at all when the history is empty", () => {
    // The failure mode worth protecting against: the page asserting an improvement
    // the database cannot back up.
    renderAudit([]);
    expect(screen.queryByText("88")).not.toBeInTheDocument();
    expect(screen.queryByText("96")).not.toBeInTheDocument();
    expect(screen.queryByText(DELTA_RE)).not.toBeInTheDocument();
  });

  it("links a measured step to its real report", () => {
    renderAudit(historyFor([88, 96]));
    const id = CASE_STUDY.steps.find((s) => s.scanId)!.scanId;
    const link = screen.getAllByRole("link", { name: "See this report" })[0];
    expect(link).toHaveAttribute("href", `/scans/${id}/report`);
  });

  it("offers no report link for a step that was never measured", () => {
    renderAudit(historyFor([88, 96]));
    const pending = CASE_STUDY.steps.find((s) => !s.scanId);
    if (!pending) return;
    const li = screen.getByRole("heading", { name: pending.title }).closest("li") as HTMLElement;
    expect(within(li).queryByRole("link", { name: "See this report" })).not.toBeInTheDocument();
    expect(within(li).getByText("Not deployed yet")).toBeInTheDocument();
  });

  it("says so when a step's scan has disappeared", () => {
    renderAudit([]);
    expect(screen.getAllByText("Scan no longer available").length).toBeGreaterThan(0);
  });

  it("shows each step's evidence lines", () => {
    renderAudit(historyFor([88, 96]));
    for (const line of CASE_STUDY.steps.flatMap((s) => s.evidence ?? [])) {
      expect(screen.getByText(line)).toBeInTheDocument();
    }
  });

  it("links the PRs behind a step", () => {
    renderAudit(historyFor([88, 96]));
    const pr = screen.getByRole("link", { name: "PR #15" });
    expect(pr).toHaveAttribute("href", "https://github.com/lyl4cs/sn0wy/pull/15");
    expect(pr).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });
});
