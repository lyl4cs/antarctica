/**
 * Route table. Every page shares the header from <Layout />.
 *
 *   /                    Home: start a scan, recent scans
 *   /scans/:id           Live scan status (polls the API)
 *   /scans/:id/report    Score, metrics, findings, AI fixes
 *   /history?url=...     One site's scans over time, before/after
 *
 * This is a single-page app: the server (Vercel) returns index.html for every path
 * (see vercel.json rewrites) and React Router picks the page in the browser.
 */
import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { HistoryPage } from "./pages/HistoryPage";
import { NotFound } from "./pages/NotFound";
import { ReportPage } from "./pages/ReportPage";
import { ScanPage } from "./pages/ScanPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="scans/:id" element={<ScanPage />} />
        <Route path="scans/:id/report" element={<ReportPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
