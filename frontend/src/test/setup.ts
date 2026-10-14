// Runs before every test file: adds DOM matchers (toBeInTheDocument, ...) and
// unmounts rendered components between tests so one test's DOM can't leak.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
