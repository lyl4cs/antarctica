/**
 * `useRescan`: start a fresh scan of a URL and navigate to it.
 *
 * Used by Retry on a failed scan and by "Scan again" on the report and history
 * pages. POSTs /scans, records the new scan in the recent-scans list, then routes
 * to /scans/{id}. On failure it surfaces the message and clears `busy` so the
 * button is clickable again; on success it stays busy because the page is leaving.
 *
 * WHY IT LIVES HERE AND NOT IN ScanPage
 * It used to be exported from pages/ScanPage.tsx, which ReportPage and HistoryPage
 * imported. That is harmless until the routes become lazy chunks (see App.tsx), at
 * which point Rollup emits `import {...} from "./ScanPage-<hash>.js"` inside the
 * ReportPage and HistoryPage chunks. Opening a report would then fetch two chunks
 * instead of one, the second being the scan page's polling logic, illustrations and
 * copy tables, for the sake of an eighteen-line hook. Measured on this tree: an
 * extra 8.8 kB request on both /scans/:id/report and /history.
 *
 * Splitting it out leaves a 0.37 kB chunk the three page chunks share, so a hook
 * used by three routes costs what a hook should. lib/ is where the other shared
 * hook (useTitle) already lives.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { rememberScan } from "./recentScans";

export interface Rescan {
  rescan: (url: string) => Promise<void>;
  busy: boolean;
  error: string | null;
}

export function useRescan(): Rescan {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function rescan(url: string) {
    setBusy(true);
    setError(null);
    try {
      const s = await api.createScan(url);
      rememberScan(s);
      navigate(`/scans/${s.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start a new scan.");
      setBusy(false);
    }
  }
  return { rescan, busy, error };
}
