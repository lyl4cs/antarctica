/**
 * Entry point: mounts <App /> inside the browser router and loads the stylesheet.
 *
 * <Analytics /> is Vercel Web Analytics: page views and unique visitors, no
 * cookies (so no consent banner), nothing sent outside Vercel. It only reports
 * once Analytics is enabled for the project in the Vercel dashboard, and does
 * nothing in local dev or tests. Visitors, not scans: scan usage comes from
 * GET /stats on the API.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Analytics } from "@vercel/analytics/react";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
    <Analytics />
  </StrictMode>,
);
