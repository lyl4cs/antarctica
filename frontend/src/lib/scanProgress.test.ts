import { describe, expect, it } from "vitest";
import { mood, steps, ticks } from "./scanProgress";

describe("scan progress view-model", () => {
  it("moves the current step along", () => {
    expect(steps("queued").map((s) => s.state)).toEqual(["current", "todo", "todo"]);
    expect(steps("running").map((s) => s.state)).toEqual(["done", "current", "todo"]);
    expect(steps("ready").map((s) => s.state)).toEqual(["done", "done", "done"]);
  });
  it("maps phases to penguin moods", () => {
    expect([mood("queued"), mood("running"), mood("ready")]).toEqual(["sleep", "awake", "happy"]);
  });
  it("draws 31 bars, blue up to the elapsed time", () => {
    const t = ticks("running", 20);
    expect(t).toHaveLength(31);
    expect(t[0].c).toBe("#2F7FB9");
    expect(t[10].c).toBe("#12202B"); // 20 s: the bar at "now"
    expect(t[30].c).toBe("#D6CFC0");
    expect(ticks("queued", 0).every((x) => x.c === "#D6CFC0")).toBe(true);
  });
});
