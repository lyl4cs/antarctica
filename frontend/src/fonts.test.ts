/**
 * Guards the self-hosted font setup against the ways it fails silently.
 *
 * WHY THIS EXISTS
 * Fonts are the one asset that breaks without breaking anything. If a family name
 * stops matching, nothing 404s and nothing throws: the page just renders in
 * system-ui and nobody notices until they look at it. So these assertions check the
 * wiring rather than any rendered output.
 *
 * WHAT IT CHECKS
 * 1. styles.css asks for the family name the installed package actually declares.
 *    @fontsource-variable names its families "<Family> Variable", so the plain
 *    "Bricolage Grotesque" that worked with Google Fonts now matches nothing. The
 *    base family is read from each package's metadata.json, so if a package renames
 *    its family on a version bump this test fails instead of the live site.
 * 2. Every weight styles.css asks for falls inside the package's variable wght axis.
 *    styles.css uses 650, which no static weight set can render.
 * 3. index.html references no third-party font origin. Re-adding a Google Fonts
 *    <link> would restore the render-blocking round trip and leave the self-hosted
 *    copies as dead weight downloaded alongside it.
 *
 * Files are read with Vite's `?raw` imports rather than node:fs, because this project
 * has no @types/node and `?raw` is typed by vite/client. Vitest stubs CSS imports to
 * "" by default, so vite.config.ts opts styles.css into real processing.
 */
import { describe, expect, it } from "vitest";

import bricolageMeta from "@fontsource-variable/bricolage-grotesque/metadata.json";
import instrumentMeta from "@fontsource-variable/instrument-sans/metadata.json";
import jetbrainsMeta from "@fontsource-variable/jetbrains-mono/metadata.json";
import indexHtml from "../index.html?raw";
import mainTsx from "./main.tsx?raw";
import styles from "./styles.css?raw";

interface FontMeta {
  family: string;
  variable?: { wght?: { min: string; max: string } };
}

/** Each entry: the specifier main.tsx imports, and that package's metadata. */
const PACKAGES: ReadonlyArray<readonly [specifier: string, meta: FontMeta]> = [
  ["@fontsource-variable/bricolage-grotesque", bricolageMeta],
  ["@fontsource-variable/instrument-sans", instrumentMeta],
  ["@fontsource-variable/jetbrains-mono", jetbrainsMeta],
];

/** Every numeric font-weight styles.css declares. */
function declaredWeights(css: string): number[] {
  return [...css.matchAll(/font-weight:\s*(\d+)\s*;/g)].map((m) => Number(m[1]));
}

describe("self-hosted fonts", () => {
  it.each(PACKAGES)("%s is imported so Vite bundles its @font-face rules", (specifier) => {
    expect(mainTsx).toContain(`"${specifier}"`);
  });

  it.each(PACKAGES)("%s's family name is the one styles.css asks for", (_s, meta) => {
    // The actual trap: "Bricolage Grotesque" != "Bricolage Grotesque Variable".
    expect(styles).toContain(`"${meta.family} Variable"`);
  });

  it.each(PACKAGES)("%s exposes a variable wght axis", (_s, meta) => {
    expect(meta.variable?.wght).toBeDefined();
  });

  it("asks for no weight outside every family's variable range", () => {
    const weights = declaredWeights(styles);
    // Catches the file being emptied by a stubbed CSS import rather than passing
    // vacuously, and pins the weight that makes the variable build necessary.
    expect(weights).toContain(650);
    for (const [specifier, meta] of PACKAGES) {
      const axis = meta.variable?.wght;
      if (!axis) throw new Error(`${specifier} has no wght axis`);
      for (const w of weights) {
        expect(w, `${specifier} cannot render font-weight: ${w}`)
          .toBeGreaterThanOrEqual(Number(axis.min));
        expect(w, `${specifier} cannot render font-weight: ${w}`)
          .toBeLessThanOrEqual(Number(axis.max));
      }
    }
  });

  it("loads no fonts from a third-party origin", () => {
    expect(indexHtml).not.toContain("fonts.googleapis.com");
    expect(indexHtml).not.toContain("fonts.gstatic.com");
    expect(indexHtml).not.toMatch(/<link[^>]+rel="stylesheet"/);
  });
});
