/**
 * Example reports shown on the home page, so a first-time visitor (a recruiter,
 * an interviewer) sees real results without scanning anything.
 *
 * HOW TO CHANGE THEM
 * Each entry is a real scan id from the live deployment. Open a report on the
 * site, copy the id from the URL (/scans/<id>/report), and add or replace an
 * entry below. Good candidates: Novus before AND after its fixes, a fast site
 * for contrast. A card whose report can't be loaded is simply hidden, so a bad id
 * never shows an error on the home page.
 */

/**
 * The worked example: sn0wy pointed at its own site, round after round.
 *
 * WHAT IS AUTHORED HERE AND WHAT IS NOT
 * Only the NARRATIVE lives in this file: which scan, in what order, what was
 * changed, and what it cost. Scores and dates are NOT stored here. The showcase
 * looks each `scanId` up in the site's live history and renders the score the API
 * reports right now (see components/SelfAudit.tsx).
 *
 * That split is deliberate. A hardcoded "88 -> 96" is a number nobody can check and
 * that silently rots the moment a scan is re-run or removed. Reading it from the
 * API means the page cannot claim an improvement the database does not support: a
 * scan that no longer exists renders as unknown instead of as a score.
 *
 * `evidence` lines are different: they describe one historical scan, which does not
 * change, so they are written down. Numbers taken from the scan are stated plainly;
 * anything measured somewhere else (a local build, a test run) says where it came
 * from, so no line implies the audit found something it did not.
 *
 * HOW TO ADD A STEP
 * 1. Deploy the change.
 * 2. Scan https://www.sn0wy.dev/ again (the www host, NOT the apex: the apex
 *    308-redirects to www and the scan is penalised for the redirect).
 * 3. Copy the scan id out of the URL and append a step below.
 * A step with an empty `scanId` renders as pending, which is how work that is
 * merged but not yet deployed stays visible instead of being quietly dropped.
 */
export interface CaseStudyStep {
  /** A real scan id from the live deployment, or "" for work not yet measured. */
  scanId: string;
  /** Short name for what changed in this round. */
  title: string;
  /** What was done, in plain terms. */
  detail: string;
  /**
   * Measured facts about this round. Frozen: a past scan does not change.
   * A line whose number did not come from the scan itself says where it did.
   */
  evidence?: string[];
  /** PR numbers behind the change, linked to the repo. */
  prs?: number[];
}

export interface CaseStudy {
  url: string;
  label: string;
  note: string;
  steps: CaseStudyStep[];
}

export const REPO_URL = "https://github.com/lyl4cs/sn0wy";

export const CASE_STUDY: CaseStudy = {
  url: "https://www.sn0wy.dev/",
  label: "www.sn0wy.dev",
  note: "Every fix below came from sn0wy's own report on itself",
  steps: [
    {
      scanId: "9c1dfc0b-f7e4-41b5-bb3c-35b270bb0a1b",
      title: "Baseline",
      detail:
        "The first scan, before any of its own advice had been taken. Three findings, " +
        "worth about 1.5 seconds and 63 KB between them.",
      evidence: [
        "Render-blocking Google Fonts stylesheet: 1,533 ms",
        "Unused JavaScript: 59.6 KB",
        "Uncompressed API response: 3.3 KB",
      ],
    },
    {
      scanId: "7a52d4f2-a0a7-425b-b0ba-926e638a82b1",
      title: "Self-hosted fonts, split routes",
      detail:
        "The webfonts moved off fonts.googleapis.com into the bundle, removing a " +
        "blocking round trip to a second origin. The three inner routes became lazy " +
        "chunks, so the home page no longer ships them.",
      evidence: [
        "Render-blocking finding: gone",
        "Unused JavaScript: 59.6 KB → 47.8 KB",
        "Entry bundle at build: 103.2 KB → 92.8 KB gzipped",
      ],
      prs: [15, 16],
    },
    {
      scanId: "483b0735-5157-4cbb-bf26-a99c24c6f5d7",
      title: "Compressed the API",
      detail:
        "The last finding was never about this page: it was an API response on " +
        "another host, which Cloud Run does not compress on its own. GZipMiddleware " +
        "on the API removed it. Three findings down to one.",
      evidence: [
        "Text-compression finding: gone",
        "Findings: 3 → 1",
        "Measured on Lighthouse 12.8.2; earlier scans ran an unrecorded 12.x",
      ],
      prs: [17],
    },
  ],
};

/**
 * Ready to show? A progression needs at least two scans that actually happened.
 * One measured point is a reading, not a story, and pending steps prove nothing.
 */
export function hasCaseStudy(c: CaseStudy = CASE_STUDY): boolean {
  return Boolean(c.url) && c.steps.filter((s) => s.scanId).length >= 2;
}

export interface ExampleReport {
  scanId: string;
  label: string;
  note?: string;
}

export const EXAMPLES: ExampleReport[] = [
  {
    scanId: "db95b809-46d4-41c7-99ca-6d128f42bfb2",
    label: "shopnovus.us",
    note: "Real e-commerce store, before optimization",
  },
  {
    scanId: "e1ea6c72-17b1-4d5e-a8f1-68717691ef22",
    label: "example.com",
    note: "Baseline: a minimal page scores 100",
  },
];
