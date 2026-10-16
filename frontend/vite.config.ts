/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite serves the app in dev (`npm run dev`, port 5173) and bundles it to dist/ for
// Vercel (`npm run build`). The `test` block configures Vitest, which reuses this
// same config so tests compile TSX exactly like the app does.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    // Vitest stubs CSS imports to "" by default, which also empties `?raw`.
    // src/fonts.test.ts reads styles.css as text to check the font-family names
    // against the installed @fontsource packages, so that one file is processed.
    // (no `$` anchor: the module id carries the `?raw` query)
    css: { include: [/styles\.css/] },
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    unstubGlobals: true,
    // Date labels depend on the time zone; pin it so tests pass on any machine.
    env: { TZ: "UTC" },
  },
});
