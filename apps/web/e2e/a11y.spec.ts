import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * WCAG 2.2 AA scans of the redesigned screens. This spec runs in both projects, so every page
 * is checked at desktop and at phone size.
 */

type Fixture = Record<string, string>;

function fixture(): Fixture {
  return JSON.parse(process.env.E2E_LINKS ?? "{}") as Fixture;
}

/** Waits for entry animations to finish, so axe measures colours at rest rather than mid-fade. */
async function settle(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const running = document
      .getAnimations()
      .some(
        (animation) =>
          animation.playState === "running" &&
          animation.effect?.getTiming().iterations !== Infinity,
      );
    // Entry animations start from opacity 0 (set before hydration), so anything visible and
    // below full opacity is still on its way in.
    const fading = Array.from(
      document.querySelectorAll<HTMLElement>('[style*="opacity"]'),
    ).some(
      (element) =>
        element.checkVisibility() &&
        Number.parseFloat(element.style.opacity) < 1,
    );
    // Streamed content replaces its skeleton later and then fades in.
    const loading = Array.from(
      document.querySelectorAll<HTMLElement>(".animate-pulse"),
    ).some((element) => element.checkVisibility());
    return !running && !fading && !loading;
  });
}

async function expectAccessible(page: Page): Promise<void> {
  // Next streams the <title> for dynamic pages, so wait for it before scanning.
  await expect(page).toHaveTitle(/\S/);
  await settle(page);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test("the staff overview and the patient sheet are accessible", async ({
  page,
}) => {
  await page.goto("/login");
  await expectAccessible(page);
  await page.getByLabel("Email").fill(fixture().staff_email ?? "");
  await page.getByLabel("Password").fill(fixture().staff_password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard$/);

  await expect(
    page.getByRole("heading", { level: 1, name: "Overview" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Kavya Test" }),
  ).toBeVisible();
  await expectAccessible(page);

  await page
    .getByRole("link", { name: "Open Kavya Test" })
    .click({ noWaitAfter: true });
  const sheet = page.getByRole("dialog", { name: "Kavya Test" });
  await expect(sheet).toBeVisible();
  await expectAccessible(page);
  await sheet.getByRole("tab", { name: "Prep timeline" }).click();
  await expectAccessible(page);
});

test("every portal tab is accessible", async ({ page }, testInfo) => {
  // Magic links are single-use, so each project has its own patient.
  const key =
    testInfo.project.name === "desktop-chrome" ? "a11y_desktop" : "a11y_mobile";
  const url = new URL(fixture()[key] ?? "");
  await page.goto(`${url.pathname}${url.hash}`);
  await page.waitForURL(/\/p\/home$/);

  const tabs = page.getByRole("navigation", { name: "Sections" });
  for (const [name, path] of [
    ["Home", /\/p\/home$/],
    ["My prep", /\/p\/prep$/],
    [/^Updates/, /\/p\/updates$/],
    ["Help", /\/p\/help$/],
  ] as const) {
    await tabs
      .getByRole("link", { name, exact: typeof name === "string" })
      .click();
    await expect(page).toHaveURL(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectAccessible(page);
  }
});
