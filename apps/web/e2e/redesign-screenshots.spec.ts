import { mkdirSync } from "node:fs";
import path from "node:path";

import { devices, type Page, test } from "@playwright/test";

/**
 * Before-and-after screenshots for the UI redesign, at desktop and phone sizes. They run on
 * purpose, never in CI:
 *
 *   SCREENSHOTS=1 SHOTS_SET=before corepack pnpm --filter @prefix/web exec playwright test redesign-screenshots
 *
 * The waits use URLs and the network, not headings, so the same spec works for both designs.
 * Everything shown is the throwaway hospital from the end-to-end fixture.
 */
const RUN = process.env.SCREENSHOTS === "1";
const SET = process.env.SHOTS_SET ?? "after";
const OUT = path.resolve(
  process.cwd(),
  "..",
  "..",
  "docs",
  "screenshots",
  "redesign",
  SET,
);
const BASE = "http://localhost:3000";

test.skip(!RUN, "Set SCREENSHOTS=1 to take the redesign screenshots.");

type Fixture = Record<string, string>;

function fixture(): Fixture {
  return JSON.parse(process.env.E2E_LINKS ?? "{}") as Fixture;
}

function portalPath(key: string): string {
  const url = new URL(fixture()[key]);
  return `${url.pathname}${url.hash}`;
}

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  // Let entrance animations finish.
  await page.waitForTimeout(600);
}

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(OUT, { recursive: true });
  await settle(page);
  await page.screenshot({ path: path.join(OUT, `${name}.png`) });
}

async function signIn(page: Page): Promise<void> {
  const links = fixture();
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(links.staff_email ?? "");
  await page.getByLabel("Password").fill(links.staff_password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard/);
}

async function firstHref(page: Page, selector: string): Promise<string | null> {
  return page
    .locator(selector)
    .first()
    .getAttribute("href", { timeout: 10_000 })
    .catch(() => null);
}

const SIZES = {
  desktop: { viewport: { width: 1280, height: 800 } },
  mobile: {
    viewport: devices["Pixel 7"].viewport,
    deviceScaleFactor: devices["Pixel 7"].deviceScaleFactor,
    isMobile: true,
    hasTouch: true,
    userAgent: devices["Pixel 7"].userAgent,
  },
} as const;

const STAFF_PAGES = [
  ["tasks", "/dashboard/tasks"],
  ["requests", "/dashboard/requests"],
  ["inbox", "/dashboard/inbox"],
  ["waitlist", "/dashboard/waitlist"],
  ["protocols", "/dashboard/protocols"],
  ["analytics", "/dashboard/analytics"],
  ["import", "/dashboard/imports"],
] as const;

const PORTAL_PAGES = [
  ["portal-prep", "/p/prep"],
  ["portal-updates", "/p/updates"],
  ["portal-help", "/p/help"],
] as const;

for (const [size, use] of Object.entries(SIZES)) {
  test.describe(`${size}`, () => {
    test.use(use);

    test("login", async ({ page }) => {
      await page.goto(`${BASE}/login`);
      await shot(page, `${size}-01-login`);
    });

    test("staff pages", async ({ page }) => {
      test.setTimeout(120_000);
      await signIn(page);
      await page.goto(`${BASE}/dashboard`);
      await shot(page, `${size}-02-overview`);

      const drawer = await firstHref(page, 'a[href*="appointment="]');
      if (drawer) {
        await page.goto(`${BASE}${drawer}`);
        await shot(page, `${size}-03-patient`);
      }

      let index = 4;
      for (const [name, route] of STAFF_PAGES) {
        const response = await page.goto(`${BASE}${route}`);
        if (response && response.status() < 400) {
          await shot(page, `${size}-${String(index).padStart(2, "0")}-${name}`);
        }
        index += 1;
      }

      await page.goto(`${BASE}/dashboard/protocols`);
      const protocol = await firstHref(
        page,
        'a[href^="/dashboard/protocols/"]:not([href$="/new"])',
      );
      if (protocol) {
        await page.goto(`${BASE}${protocol}`);
        await shot(page, `${size}-11-protocol-detail`);
      }
    });

    test("patient portal", async ({ page }) => {
      test.setTimeout(120_000);
      await page.goto(portalPath(size === "desktop" ? "reuse" : "en"));
      await page.waitForURL(/\/p\/home$/);
      await shot(page, `${size}-20-portal-home`);
      let index = 21;
      for (const [name, route] of PORTAL_PAGES) {
        const response = await page.goto(`${BASE}${route}`);
        if (response && response.status() < 400) {
          await shot(page, `${size}-${index}-${name}`);
        }
        index += 1;
      }
    });
  });
}
