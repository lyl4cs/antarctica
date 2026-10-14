import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { mockFetch, scanFixture } from "../test/http";
import { ScanPage } from "./ScanPage";

function renderScan() {
  return render(
    <MemoryRouter initialEntries={["/scans/abc"]}>
      <Routes>
        <Route path="/scans/:id" element={<ScanPage />} />
        <Route path="/scans/:id/report" element={<p>REPORT PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const eyes = (container: HTMLElement, which: string) =>
  container.querySelector(`[data-eyes="${which}"]`)?.getAttribute("opacity");

describe("ScanPage", () => {
  it("queued: sleeping penguin, waiting copy, first step current", async () => {
    mockFetch((u) => (u.pathname === "/scans/abc" ? { body: scanFixture() } : undefined));
    const { container } = renderScan();
    expect(await screen.findByRole("heading", { name: "Waiting for a scanner" })).toBeInTheDocument();
    expect(screen.getByText("Queued", { selector: ".status-chip" })).toBeInTheDocument();
    expect(eyes(container, "sleep")).toBe("1");
    expect(eyes(container, "awake")).toBe("0");
    expect(screen.getByText("Queued", { selector: ".step-label" }).closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("0:00")).toBeInTheDocument();
    expect(container.querySelector("[aria-live]")).not.toBeNull();
  });

  it("running: awake penguin, host in title, elapsed from created_at, attempt count", async () => {
    mockFetch(() => ({
      body: scanFixture({ status: "running", attempts: 2, created_at: new Date(Date.now() - 24_000).toISOString() }),
    }));
    const { container } = renderScan();
    expect(await screen.findByRole("heading", { name: "Measuring northwind.shop" })).toBeInTheDocument();
    expect(eyes(container, "awake")).toBe("1");
    expect(screen.getByText(/^0:2[45]$/)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("done: happy penguin and report button, then moves to the report", async () => {
    const created = new Date(Date.now() - 60_000);
    mockFetch(() => ({
      body: scanFixture({
        status: "done",
        attempts: 1,
        duration_ms: 38_000,
        created_at: created.toISOString(),
        finished_at: new Date(created.getTime() + 41_000).toISOString(),
      }),
    }));
    const { container } = renderScan();
    expect(await screen.findByRole("heading", { name: "Done. Here’s what we found." })).toBeInTheDocument();
    expect(eyes(container, "happy")).toBe("1");
    expect(screen.getByText("0:41")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /your report is ready/i })).toHaveAttribute("href", "/scans/abc/report");
    expect(await screen.findByText("REPORT PAGE", undefined, { timeout: 3000 })).toBeInTheDocument();
  });

  it("failed: real error, attempts, timings and a retry that starts a new scan", async () => {
    const created = new Date(2026, 9, 14, 15, 24, 0);
    const calls = mockFetch((_u, init) => {
      if (init?.method === "POST") return { status: 202, body: scanFixture({ id: "new" }) };
      return {
        body: scanFixture({
          status: "failed",
          attempts: 3,
          error: "Navigation timeout of 45000 ms exceeded",
          created_at: created.toISOString(),
          finished_at: new Date(created.getTime() + 112_000).toISOString(),
        }),
      };
    });
    renderScan();
    expect(await screen.findByRole("heading", { name: "This scan didn’t finish" })).toBeInTheDocument();
    expect(screen.getByText("Navigation timeout of 45000 ms exceeded")).toBeInTheDocument();
    expect(screen.getByText(/We tried 3 times/)).toBeInTheDocument();
    expect(screen.getByText("1 m 52 s")).toBeInTheDocument();
    screen.getByRole("button", { name: /retry scan/i }).click();
    await waitFor(() => expect(calls.mock.calls.some(([, i]) => i?.method === "POST")).toBe(true));
    const post = calls.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(JSON.parse(post[1]!.body as string)).toEqual({ url: "https://northwind.shop/" });
  });

  it("polls until the scan finishes", async () => {
    let n = 0;
    mockFetch(() => {
      n += 1;
      return { body: scanFixture({ status: n < 2 ? "running" : "failed", error: "boom", attempts: 1 }) };
    });
    renderScan();
    expect(await screen.findByRole("heading", { name: "Measuring northwind.shop" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "This scan didn’t finish" }, { timeout: 3500 })).toBeInTheDocument();
  });

  it("unknown id: not-found error", async () => {
    mockFetch(() => ({ status: 404, body: { detail: "scan not found" } }));
    renderScan();
    expect(await screen.findByRole("alert")).toHaveTextContent("Scan not found");
  });
});
