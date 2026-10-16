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
 *
 * CODE SPLITTING
 * The three inner pages are `lazy()`, so Rollup emits each as its own chunk that is
 * fetched the first time you navigate to it. The audit's "unused JavaScript" finding
 * was really this: a first-time visitor on "/" downloaded and parsed the report page
 * and the history page (chart building, markdown rendering, condition comparison)
 * before seeing the form they came for. Measured on this tree, the entry chunk goes
 * from 333.4 kB to 293.0 kB raw (103.2 kB to 92.8 kB gzipped) and the three pages
 * become chunks of 8.6 / 13.4 / 18.1 kB fetched on first visit to each route.
 *
 * What is left in the entry chunk is mostly React and React Router, which every
 * route needs, so splitting cannot remove it. That is why the saving is ~40 kB and
 * not the ~60 kB the audit estimated for the finding.
 *
 * Home and NotFound stay eager on purpose. Home is where almost everyone lands, so
 * splitting it would only move its bytes behind an extra round trip on the critical
 * path, and NotFound is fifteen lines. Splitting a route is a trade: fewer bytes up
 * front, one more request when you navigate. It pays off for pages most visitors
 * never open, and costs you on the page they always open.
 *
 * `Suspense` sits inside <Layout />'s route so the header stays on screen while a
 * chunk loads, instead of the whole frame blanking.
 */
import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Loading } from "./components/States";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";

const ScanPage = lazy(() =>
  import("./pages/ScanPage").then((m) => ({ default: m.ScanPage })),
);
const ReportPage = lazy(() =>
  import("./pages/ReportPage").then((m) => ({ default: m.ReportPage })),
);
const HistoryPage = lazy(() =>
  import("./pages/HistoryPage").then((m) => ({ default: m.HistoryPage })),
);

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route
          path="scans/:id"
          element={
            <Suspense fallback={<Loading label="Loading the scan…" />}>
              <ScanPage />
            </Suspense>
          }
        />
        <Route
          path="scans/:id/report"
          element={
            <Suspense fallback={<Loading label="Loading the report…" />}>
              <ReportPage />
            </Suspense>
          }
        />
        <Route
          path="history"
          element={
            <Suspense fallback={<Loading label="Loading the history…" />}>
              <HistoryPage />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
