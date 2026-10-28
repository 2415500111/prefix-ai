import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against a real API and Postgres (see e2e/global-setup.ts).
 * Run `pnpm --filter @prefix/web build` first: the web app is served with `next start`.
 */
const WEB_PORT = 3000;
const API_PORT = 8000;

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: true,
  // Cold starts and parallel workers make the 30-second default too tight for flows that log in first.
  timeout: 60_000,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  // A typical low-end Android phone screen.
  projects: [
    // The patient portal is mobile-first: test it at a phone size.
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 7"] },
      testIgnore: /(coordinator|guest|analytics|waitlist|imports)\.spec\.ts/,
    },
    // Staff screens are desktop-first.
    {
      name: "desktop-chrome",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /(coordinator|guest|analytics|waitlist|imports)\.spec\.ts/,
    },
  ],
  webServer: [
    {
      command: `uv run uvicorn prefix_api.main:create_app --factory --port ${API_PORT}`,
      cwd: "../..",
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `node ./node_modules/next/dist/bin/next start --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
