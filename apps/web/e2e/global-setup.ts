import { execFileSync } from "node:child_process";
import path from "node:path";

// Playwright loads this file as CommonJS, so __dirname is available.
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

/** Creates fresh portal data (a new organization each run) and shares the magic links. */
export default function globalSetup(): void {
  const output = execFileSync(
    "uv",
    ["run", "python", "scripts/e2e_portal_fixture.py"],
    { cwd: REPO_ROOT, encoding: "utf8" },
  );
  const lastLine = output.trim().split("\n").at(-1) ?? "";
  // Validate before handing to the tests (workers inherit process.env).
  const links = JSON.parse(lastLine) as Record<string, string>;
  for (const key of [
    "en",
    "hi",
    "reuse",
    "assist",
    "message",
    "a11y_desktop",
    "a11y_mobile",
  ]) {
    if (!links[key]?.includes("#token=")) {
      throw new Error(`Fixture did not return a "${key}" magic link`);
    }
  }
  process.env.E2E_LINKS = lastLine;
}
