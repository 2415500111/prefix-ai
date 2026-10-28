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

async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test("a patient confirms a step and reports a problem with a critical one", async ({
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
  const checklist = page.getByRole("region", {
    name: "Your readiness checklist",
  });
  await expect(checklist.getByText("0 of 2 done")).toBeVisible();
  await expectAccessible(page);

  await page
    .getByRole("button", { name: "Yes, done: Arrange an escort" })
    .click();
  await expect(checklist.getByText("1 of 2 done")).toBeVisible();

  await page
    .getByRole("button", { name: "No / I have a problem: Clear liquids only" })
    .click();
  await page
    .getByLabel("Tell us what is wrong (optional)")
    .fill("I could not buy the prep solution");
  await page.getByRole("button", { name: "Tell my care team" }).click();

  await expect(
    page.getByText(/has been told about a problem with your preparation/),
  ).toBeVisible();
  const liquids = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "Clear liquids only" }) });
  await expect(liquids.getByText("Problem reported")).toBeVisible();
  await expectAccessible(page);
});

test("a magic link works once; the patient can add the date to a calendar and ask to reschedule", async ({
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

  await page.getByRole("button", { name: "I need to reschedule" }).click();
  await page
    .getByLabel("Anything we should know? (optional)")
    .fill("Travelling that week");
  await page.getByRole("button", { name: "Ask to reschedule" }).click();
  await expect(
    page.getByText(
      "We have asked your care team to call you about a new date.",
    ),
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
  await expect(page.getByText(/हिंदी अनुवाद अभी तैयार नहीं/)).toBeVisible();
  await expect(page.getByText("तबीयत ठीक नहीं लग रही?")).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("button", { name: "English" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Hello, Ravi" }),
  ).toBeVisible();
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
