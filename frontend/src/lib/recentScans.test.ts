import { afterEach, describe, expect, it, vi } from "vitest";
import { MAX_RECENT, STORAGE_KEY, clearRecent, forgetScans, loadRecent, rememberScan } from "./recentScans";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("recentScans", () => {
  it("keeps newest first and moves a re-remembered id to the top", () => {
    rememberScan({ id: "a", url: "https://a.com/" }, new Date("2026-10-01"));
    rememberScan({ id: "b", url: "https://b.com/" }, new Date("2026-10-02"));
    rememberScan({ id: "a", url: "https://a.com/" }, new Date("2026-10-03"));
    expect(loadRecent().map((r) => r.id)).toEqual(["a", "b"]);
    expect(loadRecent()[0].createdAt).toBe("2026-10-03T00:00:00.000Z");
  });

  it(`caps the list at ${MAX_RECENT}`, () => {
    for (let i = 0; i < MAX_RECENT + 5; i++) rememberScan({ id: `s${i}`, url: "https://a.com/" });
    const ids = loadRecent().map((r) => r.id);
    expect(ids).toHaveLength(MAX_RECENT);
    expect(ids[0]).toBe(`s${MAX_RECENT + 4}`);
  });

  it("forgets specific ids and clears everything", () => {
    rememberScan({ id: "a", url: "u" });
    rememberScan({ id: "b", url: "u" });
    forgetScans(["a"]);
    expect(loadRecent().map((r) => r.id)).toEqual(["b"]);
    clearRecent();
    expect(loadRecent()).toEqual([]);
  });

  it("ignores corrupt or foreign data in storage", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not json");
    expect(loadRecent()).toEqual([]);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([{ id: 1 }, { id: "ok", url: "u", createdAt: "t" }]));
    expect(loadRecent().map((r) => r.id)).toEqual(["ok"]);
  });

  it("never throws when storage is blocked (private mode)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    expect(loadRecent()).toEqual([]);
    expect(() => rememberScan({ id: "a", url: "u" })).not.toThrow();
    expect(() => forgetScans(["a"])).not.toThrow();
    expect(() => clearRecent()).not.toThrow();
  });
});
