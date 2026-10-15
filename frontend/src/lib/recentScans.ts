/**
 * "Your recent scans": remembered per browser, not fetched from a global list.
 *
 * WHY
 * The old home page listed the newest scans of EVERY visitor (GET /scans), which
 * leaked every URL anyone scanned (staging sites, private pages) to everyone.
 * There are no accounts, so the scans that are "yours" are simply the ones this
 * browser started: we keep their ids in localStorage and look each one up by id.
 * Scan ids are random UUIDs, so a report link is only reachable by someone you
 * share it with.
 *
 * Every storage call is wrapped in try/catch: private windows and blocked site
 * data can make localStorage throw, and the page must still work (the list is
 * just empty). See ADR 017.
 */

export interface RecentScan {
  id: string;
  url: string;
  createdAt: string; // ISO time this browser started the scan
}

export const STORAGE_KEY = "antarctica.recentScans.v1";
export const MAX_RECENT = 12;

function isRecent(x: unknown): x is RecentScan {
  const r = x as RecentScan;
  return !!r && typeof r.id === "string" && typeof r.url === "string" && typeof r.createdAt === "string";
}

export function loadRecent(): RecentScan[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isRecent) : [];
  } catch {
    return [];
  }
}

function save(list: RecentScan[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // storage unavailable or full: remembering is best-effort
  }
}

/** Newest first, de-duplicated by id, capped at MAX_RECENT. */
export function rememberScan(scan: { id: string; url: string }, now: Date = new Date()): void {
  const rest = loadRecent().filter((r) => r.id !== scan.id);
  save([{ id: scan.id, url: scan.url, createdAt: now.toISOString() }, ...rest].slice(0, MAX_RECENT));
}

export function forgetScans(ids: string[]): void {
  if (ids.length === 0) return;
  const drop = new Set(ids);
  save(loadRecent().filter((r) => !drop.has(r.id)));
}

export function clearRecent(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing to clear
  }
}
