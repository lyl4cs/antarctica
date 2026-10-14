/**
 * Test helper: a fake `fetch` that answers from a route table, so page tests run
 * offline and can assert exactly which API calls were made.
 */
import { vi } from "vitest";

export type Handler = (url: URL, init?: RequestInit) => { status?: number; body?: unknown } | undefined;

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

/** Install a fetch mock on globalThis; unmatched requests return 500 so tests fail loudly. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url);
    const r = handler(url, init);
    if (!r) return jsonResponse({ detail: `unmocked ${url.pathname}` }, 500);
    return jsonResponse(r.body ?? null, r.status ?? 200);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const scanFixture = (over: Record<string, unknown> = {}) => ({
  id: "abc",
  url: "https://northwind.shop/",
  status: "queued",
  attempts: 0,
  error: null,
  duration_ms: null,
  created_at: new Date(Date.now() - 5000).toISOString(),
  finished_at: null,
  ...over,
});
