import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EXAMPLES } from "../examples";
import { loadRecent, rememberScan } from "../lib/recentScans";
import { mockFetch, scanFixture } from "../test/http";
import { Home } from "./Home";

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

const renderHome = () =>
  render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  );

const report = (id: string, score: number) => ({
  scan: scanFixture({ id, status: "done" }),
  performance_score: score,
  metrics: {},
  findings: [],
});

describe("Home", () => {
  it("shows only this browser's scans, never a global list", async () => {
    rememberScan({ id: "mine-done", url: "https://mine.test/" });
    rememberScan({ id: "mine-running", url: "https://wip.test/" });
    const fetchFn = mockFetch((u) => {
      if (u.pathname === "/scans/mine-done") return { body: scanFixture({ id: "mine-done", url: "https://mine.test/", status: "done" }) };
      if (u.pathname === "/scans/mine-done/report") return { body: report("mine-done", 88) };
      if (u.pathname === "/scans/mine-running") return { body: scanFixture({ id: "mine-running", url: "https://wip.test/", status: "running" }) };
      return { status: 404, body: { detail: "scan not found" } }; // examples: hidden
    });
    renderHome();
    expect(await screen.findByRole("heading", { name: "Your recent scans" })).toBeInTheDocument();
    expect(await screen.findByText("mine.test")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
    expect(screen.getByText("wip.test")).toBeInTheDocument();
    const paths = fetchFn.mock.calls.map((c) => new URL(String(c[0])).pathname);
    expect(paths).not.toContain("/scans"); // the removed global listing is never called
  });

  it("drops remembered scans that no longer exist", async () => {
    rememberScan({ id: "gone", url: "https://gone.test/" });
    mockFetch(() => ({ status: 404, body: { detail: "scan not found" } }));
    renderHome();
    expect(await screen.findByText(/stay private to you/)).toBeInTheDocument();
    await waitFor(() => expect(loadRecent()).toEqual([]));
  });

  it("clear empties the list", async () => {
    rememberScan({ id: "a", url: "https://a.test/" });
    mockFetch((u) =>
      u.pathname === "/scans/a" ? { body: scanFixture({ id: "a", url: "https://a.test/", status: "queued" }) } : { status: 404 },
    );
    renderHome();
    fireEvent.click(await screen.findByRole("button", { name: "Clear" }));
    expect(screen.getByText(/stay private to you/)).toBeInTheDocument();
    expect(loadRecent()).toEqual([]);
  });

  it("shows example reports with live scores and hides ones that fail", async () => {
    const [ok, broken] = EXAMPLES;
    mockFetch((u) => {
      if (u.pathname === `/scans/${ok.scanId}/report`) return { body: report(ok.scanId, 71) };
      if (broken && u.pathname === `/scans/${broken.scanId}/report`) return { status: 500 };
      return undefined;
    });
    renderHome();
    expect(await screen.findByRole("heading", { name: "Example reports" })).toBeInTheDocument();
    expect(screen.getByText(ok.label)).toBeInTheDocument();
    expect(screen.getByText("71")).toBeInTheDocument();
    if (broken) expect(screen.queryByText(broken.label)).not.toBeInTheDocument();
  });

  it("remembers a scan when the form starts one", async () => {
    mockFetch((u, init) =>
      u.pathname === "/scans" && init?.method === "POST"
        ? { status: 202, body: scanFixture({ id: "new1", url: "https://new.test/" }) }
        : { status: 404 },
    );
    renderHome();
    fireEvent.change(screen.getByLabelText("Website URL"), { target: { value: "https://new.test" } });
    fireEvent.click(screen.getByRole("button", { name: /Scan site/ }));
    await waitFor(() => expect(loadRecent().map((r) => r.id)).toEqual(["new1"]));
  });
});
