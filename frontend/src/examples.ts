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
 * The worked example: one real site scanned, fixed using sn0wy's own suggestions,
 * then scanned again. It links to the history compare so a first-time visitor sees
 * what the whole loop looks like, not just a single report.
 *
 * HOW TO FILL IT IN
 * 1. Scan the site. Copy the scan id from the URL. That is `beforeScanId`.
 * 2. Apply the fixes it suggested.
 * 3. Scan again. That id is `afterScanId`.
 * Leave `afterScanId` empty until step 3 is really done. The card hides itself
 * while either id is missing, so a half-finished case study never ships.
 */
export interface CaseStudy {
  url: string;
  label: string;
  beforeScanId: string;
  afterScanId: string;
  note: string;
}

export const CASE_STUDY: CaseStudy = {
  url: "",
  label: "",
  beforeScanId: "",
  afterScanId: "",
  note: "Scanned, fixed with sn0wy's own suggestions, then scanned again",
};

/** Ready to show? Both ends of the before/after have to exist. */
export function hasCaseStudy(c: CaseStudy = CASE_STUDY): boolean {
  return Boolean(c.url && c.beforeScanId && c.afterScanId);
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
