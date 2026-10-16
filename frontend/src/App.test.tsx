/**
 * Tests the route table, with an eye on the thing code splitting can quietly break.
 *
 * A `lazy()` route renders nothing on its first frame. Without a `Suspense`
 * boundary above it React throws; with one too high up, the whole frame including
 * the header blanks while the chunk downloads. Both are invisible in a dev build
 * where chunks resolve instantly from memory, so these tests assert on the
 * intermediate frame rather than only the settled one: the fallback and the shared
 * header have to be on screen together, then the page replaces the fallback.
 *
 * The chunk boundaries themselves are a bundler outcome and are checked by
 * `vite build`, not here. What is checkable here is that every lazy route resolves
 * to a real component, which is what a wrong named export in the
 * `lazy(() => import(...).then(m => ({ default: m.X })))` dance gets wrong: the
 * fallback would simply never be replaced.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { mockFetch, scanFixture } from "./test/http";
import { App } from "./App";

/** Answers whatever each page asks for on mount, so nothing throws past the split. */
function stubApi() {
  return mockFetch((u) => {
    if (u.pathname === "/scans/abc") return { body: scanFixture() };
    if (u.pathname === "/scans/abc/report") return { status: 409, body: { detail: "queued" } };
    if (u.pathname === "/sites/scans") return { body: [] };
    if (u.pathname === "/stats") return { body: {} };
    return undefined;
  });
}

function renderAt(path: string) {
  stubApi();
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

const LAZY_ROUTES = [
  ["/scans/abc", "Loading the scan…"],
  ["/scans/abc/report", "Loading the report…"],
  ["/history?url=https%3A%2F%2Fa.test%2F", "Loading the history…"],
] as const;

describe("App routing", () => {
  it.each(LAZY_ROUTES)("%s shows a fallback while its chunk loads", (path, label) => {
    renderAt(path);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it.each(LAZY_ROUTES)("%s keeps the shared header during the fallback", (path, label) => {
    renderAt(path);
    // Suspense sits inside the Layout route, so the header must not blank out.
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it.each(LAZY_ROUTES)("%s resolves its lazy chunk to a real page", async (path, label) => {
    renderAt(path);
    await waitFor(() => {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    });
  });

  it("renders Home eagerly, with no fallback frame on the landing route", () => {
    renderAt("/");
    expect(screen.queryByText(/^Loading the /)).not.toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("renders NotFound eagerly for an unknown path", () => {
    renderAt("/nope");
    expect(screen.queryByText(/^Loading the /)).not.toBeInTheDocument();
  });
});
