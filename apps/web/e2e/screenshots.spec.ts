import { mkdirSync } from "node:fs";
import path from "node:path";

import { devices, expect, type Page, test } from "@playwright/test";

/**
 * Screenshots for the README and docs/screenshots/. They run on purpose, never in CI:
 *
 *   SCREENSHOTS=1 corepack pnpm --filter @prefix/web exec playwright test screenshots
 *
 * They use the throwaway test hospital from the end-to-end fixture, so every name in the
 * pictures is made up.
 */
const RUN = process.env.SCREENSHOTS === "1";
const OUT = path.resolve(process.cwd(), "..", "..", "docs", "screenshots");
const BASE = "http://localhost:3000";

test.skip(!RUN, "Set SCREENSHOTS=1 to take the README screenshots.");

type Fixture = Record<string, string>;

function fixture(): Fixture {
  return JSON.parse(process.env.E2E_LINKS ?? "{}") as Fixture;
}

function portalPath(key: "en" | "hi" | "assist"): string {
  const url = new URL(fixture()[key]);
  return `${url.pathname}${url.hash}`;
}

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, name) });
}

/** Lets entrance animations and late requests finish before a screenshot. */
async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(600);
}

function tabBar(page: Page) {
  return page.getByRole("navigation", { name: "Sections" });
}

async function signInAsCoordinator(page: Page): Promise<void> {
  const links = fixture();
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(links.staff_email ?? "");
  await page.getByLabel("Password").fill(links.staff_password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard$/);
}

test.describe("staff screens", () => {
  // In order: the dashboard is shot before the analytics test releases a booking.
  test.describe.configure({ mode: "serial" });
  test.use({ viewport: { width: 1280, height: 800 } });

  test("login page with Try as Guest", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await expect(
      page.getByRole("button", { name: "Try as Guest" }),
    ).toBeVisible();
    await shot(page, "01-login-try-as-guest.png");
  });

  test("coordinator overview and patient sheet", async ({ page }) => {
    await signInAsCoordinator(page);
    await expect(
      page.getByRole("heading", { name: "Overview", level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Open Asha Test" }),
    ).toBeVisible();
    await settle(page);
    await shot(page, "02-coordinator-dashboard.png");

    // Next navigates on the client; do not wait for a full page load after the click.
    await page
      .getByRole("link", { name: "Open Asha Test" })
      .click({ noWaitAfter: true });
    const sheet = page.getByRole("dialog", { name: "Asha Test" });
    await sheet.getByRole("tab", { name: "Prep timeline" }).click();
    await expect(sheet.getByRole("list", { name: "Prep steps" })).toBeVisible();
    await settle(page);
    await shot(page, "03-patient-drawer.png");
  });

  test("protocols", async ({ page }) => {
    await signInAsCoordinator(page);
    await page.goto(`${BASE}/dashboard/protocols`);
    await expect(
      page.getByRole("heading", { name: "Protocols", level: 1 }),
    ).toBeVisible();
    await shot(page, "04-protocols.png");
  });

  test("analytics", async ({ page }) => {
    // Release one booking with a prep-related reason, so the figures have something to show.
    await signInAsCoordinator(page);
    await page
      .getByRole("link", { name: "Open Meera Test" })
      .click({ noWaitAfter: true });
    const sheet = page.getByRole("dialog", { name: "Meera Test" });
    await sheet.getByRole("button", { name: "Cancel", exact: true }).click();
    const confirm = page.getByRole("dialog", {
      name: "Cancel Meera Test's procedure?",
    });
    await confirm.getByLabel("Reason").selectOption("ATE_OR_DRANK");
    await confirm.getByRole("button", { name: "Cancel procedure" }).click();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: /cancel|release/i })
        .first(),
    ).toBeVisible();

    // The default range is the last 30 days; the fixture's bookings are in the next few days.
    const day = (offset: number) =>
      new Date(Date.now() + offset * 24 * 60 * 60 * 1000)
        .toISOString()
        .slice(0, 10);
    await page.goto(
      `${BASE}/dashboard/analytics?start=${day(-1)}&end=${day(7)}`,
    );
    await expect(
      page.getByRole("heading", { name: "Analytics", level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByText("Prep-related cancellations").first(),
    ).toBeVisible();
    await page.waitForLoadState("networkidle");
    await shot(page, "05-analytics.png");
  });

  test("CSV import dry run", async ({ page }) => {
    await signInAsCoordinator(page);
    await page.goto(`${BASE}/dashboard/imports`);
    await expect(
      page.getByRole("heading", { name: "Import records" }),
    ).toBeVisible();
    // Wait for the page's client code before choosing the file, as the e2e spec does.
    await page.waitForLoadState("networkidle");
    await page.getByLabel("CSV file", { exact: true }).setInputFiles({
      name: "patients.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        [
          "first_name,last_name,date_of_birth,phone,consent_to_message",
          "Asha,Import,1968-03-14,+919812300001,yes",
          ",Missing,1980-01-01,,no",
        ].join("\n"),
      ),
    });
    await page.getByRole("button", { name: "Check file" }).click();
    await expect(page.getByText("1 of 2 rows are valid")).toBeVisible();
    await settle(page);
    await shot(page, "06-csv-import-dry-run.png");
  });
});

test.describe("patient portal on a phone", () => {
  // The Pixel 7 profile, set field by field: a describe group cannot take its browser type.
  const phone = devices["Pixel 7"];
  test.use({
    viewport: phone.viewport,
    deviceScaleFactor: phone.deviceScaleFactor,
    isMobile: true,
    hasTouch: true,
    userAgent: phone.userAgent,
  });

  test("home and updates in English", async ({ page }) => {
    await page.goto(portalPath("en"));
    await expect(page).toHaveURL(/\/p\/home$/);
    await settle(page);
    await shot(page, "07-portal-english-mobile.png");

    await tabBar(page).getByRole("link", { name: "Updates" }).click();
    await expect(page).toHaveURL(/\/p\/updates$/);
    await settle(page);
    await shot(page, "10-portal-updates-mobile.png");
  });

  test("prep plan in Hindi", async ({ page }) => {
    await page.goto(portalPath("hi"));
    await expect(page).toHaveURL(/\/p\/home$/);
    await settle(page);
    await shot(page, "08-portal-hindi-mobile.png");
  });

  test("AI assistant answers a question about the patient's own prep", async ({
    page,
  }) => {
    await page.goto(portalPath("assist"));
    await expect(page).toHaveURL(/\/p\/home$/);
    // The assistant lives under Help.
    await tabBar(page).getByRole("link", { name: "Help", exact: true }).click();
    await expect(page).toHaveURL(/\/p\/help$/);
    await page
      .getByLabel("Your question")
      .fill("Can I drink water before my procedure?");
    await page.getByRole("button", { name: "Send question" }).click();
    // An ordinary answer is announced as a status; the question is repeated inside it.
    const reply = page.getByRole("status").filter({ hasText: "Can I drink" });
    await expect(reply.first()).toBeVisible();
    await reply.first().scrollIntoViewIfNeeded();
    await settle(page);
    await shot(page, "09-assistant-chat-mobile.png");
  });
});
