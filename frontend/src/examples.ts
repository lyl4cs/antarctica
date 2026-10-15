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
