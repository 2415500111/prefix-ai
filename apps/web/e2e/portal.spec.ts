import { readFile } from "node:fs/promises";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

type LinkKey = "en" | "hi" | "reuse";

/** The magic link as a path, so it opens on whatever host the tests use. */
function link(key: LinkKey): string {
  const links = JSON.parse(process.env.E2E_LINKS ?? "{}") as Record<
    LinkKey,
    string
  >;
  const url = new URL(links[key]);
  return `${url.pathname}${url.hash}`;
}

async function openPortal(page: Page, key: LinkKey): Promise<void> {
  await page.goto(link(key));
  await expect(page).toHaveURL(/\/p\/home$/);
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

/** The bottom tab bar. Next keeps earlier routes mounted but hidden, so only visible links count. */
function tab(page: Page, name: string | RegExp) {
  return page
    .getByRole("navigation", { name: /^(Sections|हिस्से)$/ })
    .getByRole("link", { name, exact: typeof name === "string" });
}

test("a patient opens an update, confirms a step and reports a problem with a critical one", async ({
  page,
}) => {
  await openPortal(page, "en");
  expect(page.url()).not.toContain("token");

  await expect(
    page.getByRole("heading", { level: 1, name: "Hello, Asha" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Colonoscopy" }),
  ).toBeVisible();
  await expect(page.getByText("Your procedure is in 2 days.")).toBeVisible();
  const readiness = page.getByRole("region", { name: "Your readiness" });
  await expect(readiness.getByText("0 of 2 done")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Next step" }).getByRole("heading", {
      name: "Arrange an escort",
    }),
  ).toBeVisible();
  await expectAccessible(page);

  // Updates: the bell and the tab carry the unread count; opening one marks it read.
  await expect(
    page.getByRole("link", { name: "Updates, 3 unread" }).first(),
  ).toBeVisible();
  await tab(page, /^Updates/).click();
  await expect(page).toHaveURL(/\/p\/updates$/);
  await page
    .getByRole("button", { name: /Do this now: Arrange an escort/ })
    .click();
  const sheet = page.getByRole("dialog", {
    name: "Do this now: Arrange an escort",
  });
  await expect(sheet).toBeVisible();
  await expectAccessible(page);
  await sheet.getByRole("link", { name: "Go to this step" }).click();

  // My prep: confirm one step, report a problem with another from the bottom sheet.
  await expect(page).toHaveURL(/\/p\/prep#step-/);
  // The open sheet hid the tab bar from assistive technology; now it shows one fewer unread.
  await expect(tab(page, "Updates")).toHaveAccessibleDescription("2 unread");
  await expect(
    page.getByRole("heading", { level: 1, name: "My prep" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Yes, done: Arrange an escort" })
    .click();
  await expect(page.getByText("Marked as done")).toBeVisible();
  await expect(page.getByText("1 of 2 done")).toBeVisible();

  await page
    .getByRole("button", { name: "I have a problem: Clear liquids only" })
    .click();
  const problem = page.getByRole("dialog", { name: "Tell us about a problem" });
  await problem
    .getByLabel("Tell us what is wrong (optional)")
    .fill("I could not buy the prep solution");
  await problem.getByRole("button", { name: "Tell my care team" }).click();
  await expect(page.getByText("Your care team has been told")).toBeVisible();
  const liquids = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "Clear liquids only" }) });
  await expect(liquids.getByText("Problem reported")).toBeVisible();
  await expectAccessible(page);

  await tab(page, "Home").click();
  await expect(
    page.getByText(/has been told about a problem with your preparation/),
  ).toBeVisible();
});

test("a magic link works once; the patient adds the date to a calendar, clears updates and asks to reschedule", async ({
  page,
  browser,
}) => {
  await openPortal(page, "reuse");

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Add to calendar" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("procedure.ics");
  const ics = await readFile(await file.path(), "utf8");
  expect(ics).toContain("BEGIN:VCALENDAR");
  expect(ics).toContain("SUMMARY:Colonoscopy");

  await tab(page, /^Updates/).click();
  await expect(tab(page, "Updates")).toHaveAccessibleDescription("3 unread");
  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(tab(page, "Updates")).toHaveAccessibleDescription("");

  await tab(page, "Help").click();
  await expect(page.getByRole("link", { name: "Call 112" })).toHaveAttribute(
    "href",
    "tel:112",
  );
  await page.getByRole("button", { name: "I need to reschedule" }).click();
  const request = page.getByRole("dialog", { name: "Change your date" });
  await request
    .getByLabel("Anything we should know? (optional)")
    .fill("Travelling that week");
  await request.getByRole("button", { name: "Ask to reschedule" }).click();
  await expect(
    page.getByRole("region", { name: "Change your date" }).getByRole("status"),
  ).toHaveText(/We have asked your care team to call you/);
  await expectAccessible(page);

  await tab(page, /^Updates/).click();
  await expect(
    page.getByRole("button", {
      name: /We received your request to change the date/,
    }),
  ).toBeVisible();

  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto(link("reuse"));
  await expect(
    second.getByText(/expired or was already used/).first(),
  ).toBeVisible();
  await other.close();
});

test("the portal speaks Hindi and can switch to English", async ({ page }) => {
  await openPortal(page, "hi");

  await expect(
    page.getByRole("heading", { level: 1, name: "नमस्ते, Ravi" }),
  ).toBeVisible();
  // getByRole skips hidden elements: Next keeps the previous route mounted but hidden.
  await expect(page.getByRole("main")).toHaveAttribute("lang", "hi");
  await expect(page.getByText("तबीयत ठीक नहीं लग रही?")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "अपडेट, 3 नहीं पढ़े" }).first(),
  ).toBeVisible();
  await expectAccessible(page);

  await tab(page, "मेरी तैयारी").click();
  await expect(page.getByText(/हिंदी अनुवाद अभी तैयार नहीं/)).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("button", { name: "English" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "My prep" }),
  ).toBeVisible();
  await expect(tab(page, "Home")).toBeVisible();
});

test("without a session the portal shows how to get a new link", async ({
  page,
}) => {
  await page.goto("/p/home");

  await expect(page).toHaveURL(/\/p\/expired$/);
  await expect(
    page.getByText(/ask your care team for a new link/),
  ).toBeVisible();
});
