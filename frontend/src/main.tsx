/**
 * Entry point: mounts <App /> inside the browser router and loads the stylesheet.
 *
 * FONTS
 * The three families are imported here rather than linked from fonts.googleapis.com.
 * A <link rel="stylesheet"> to Google Fonts is render-blocking on a *third-party*
 * origin: the browser cannot start it until index.html arrives, then pays DNS + TLS +
 * the CSS round trip before it even learns which .woff2 files to fetch. Importing the
 * CSS here folds those @font-face rules into the bundle Vite already emits, so the
 * same-origin stylesheet the page was loading anyway now carries them, and the font
 * files are fetched from this origin with the app's long cache headers.
 *
 * Each package's `index.css` is the wght-axis variable file. It has to be the variable
 * build, not the static weights: styles.css asks for `font-weight: 650`, which only a
 * variable font can render (a static set would snap it to 700). `font-display: swap`
 * is already declared inside these files, so there is no flash-of-invisible-text and
 * no need for the media="print" onload trick.
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
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/instrument-sans";
import "@fontsource-variable/jetbrains-mono";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
    <Analytics />
  </StrictMode>,
);
