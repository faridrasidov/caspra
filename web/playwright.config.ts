import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  outputDir: join(tmpdir(), process.env.CASPRA_E2E_REAL === "1" ? "caspra-playwright-real" : "caspra-playwright-mock"),
  testDir: "./tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  fullyParallel: false,
  workers: process.env.CASPRA_E2E_REAL === "1" ? 1 : undefined,
  retries: 1,
  reporter: "list",
  use: {
    baseURL: process.env.CASPRA_E2E_REAL === "1" ? "http://127.0.0.1:5175" : "http://127.0.0.1:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1024 } },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
});
