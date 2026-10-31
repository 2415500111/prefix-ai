import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

/**
 * A patient raises problems in the portal; without a reload, the coordinator's bell shows the
 * newest at the top, with its time and urgent styling. This test has a hospital of its own (see
 * scripts/e2e_portal_fixture.py), so no other test adds to its bell.
 */

type Fixture = Record<string, string>;

function fixture(): Fixture {
  return JSON.parse(process.env.E2E_LINKS ?? "{}") as Fixture;
}

/** The magic link as a path, so it opens on whatever host the tests use. */
function portalLink(): string {
  const url = new URL(fixture().bell ?? "");
  return `${url.pathname}${url.hash}`;
}

async function signIn(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(fixture().bell_staff_email ?? "");
  await page.getByLabel("Password").fill(fixture().staff_password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard$/);
}

async function reportProblem(
  page: Page,
  step: string,
  note: string,
): Promise<void> {
  await page.getByRole("button", { name: `I have a problem: ${step}` }).click();
  const sheet = page.getByRole("dialog", { name: "Tell us about a problem" });
  await sheet.getByLabel("Tell us what is wrong (optional)").fill(note);
  await sheet.getByRole("button", { name: "Tell my care team" }).click();
  await expect(sheet).toBeHidden();
}

/** Waits for animations to finish, so axe measures colours at rest. */
async function expectAccessible(page: Page): Promise<void> {
  await page.waitForFunction(
    () =>
      !document
        .getAnimations()
        .some(
          (animation) =>
            animation.playState === "running" &&
            animation.effect?.getTiming().iterations !== Infinity,
        ) &&
      !Array.from(
        document.querySelectorAll<HTMLElement>('[style*="opacity"]'),
      ).some(
        (element) =>
          element.checkVisibility() &&
          Number.parseFloat(element.style.opacity) < 1,
      ),
  );
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

// "30 Oct, 1:02 pm": the facility's time.
const RAISED_AT = /\d{1,2} [A-Z][a-z]{2}, \d{1,2}:\d{2}\s(am|pm)/;

test("a problem raised in the portal reaches the top of the staff bell, with its time and urgent styling", async ({
  browser,
}) => {
  // The bell asks every 15 seconds, so allow for a couple of rounds.
  test.setTimeout(150_000);
  const staff = await browser.newContext();
  const page = await staff.newPage();
  await signIn(page);
  const bell = page.getByRole("button", { name: /^Notifications/ });
  await expect(bell).toHaveAccessibleName("Notifications");

  const patient = await browser.newContext();
  const portal = await patient.newPage();
  await portal.goto(portalLink());
  await expect(portal).toHaveURL(/\/p\/home$/);
  await portal.goto("/p/prep");
  // An ordinary step first, then a critical one a moment later.
  await reportProblem(portal, "Arrange an escort", "My son is away that day");
  await reportProblem(
    portal,
    "Clear liquids only",
    "I could not buy the prep solution",
  );
  await patient.close();

  // No reload: the open dashboard picks both up, and the urgent one raises a toast.
  await expect(bell).toHaveAccessibleName("Notifications, 2 unread, 1 urgent", {
    timeout: 45_000,
  });
  await expect(
    page.getByRole("alert").filter({ hasText: "Urgent: Sunita Test" }),
  ).toBeVisible();
  // The Overview flags the patient while the urgent item is unread.
  const row = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("link", { name: "Open Sunita Test" }) });
  await expect(row).toContainText("Unread urgent");

  await bell.click();
  const items = page
    .getByRole("list", { name: "Notifications, newest first" })
    .getByRole("link");
  await expect(items).toHaveCount(2);
  const newest = items.first();
  await expect(newest).toContainText("Sunita Test");
  await expect(newest).toContainText("Colonoscopy");
  await expect(newest).toContainText("Cannot complete: Clear liquids only");
  await expect(newest).toContainText("Urgent");
  await expect(newest).toContainText(RAISED_AT);
  await expect(newest).toContainText(/just now|\d+ min ago/);
  await expect(newest).toHaveClass(/border-l-urgent/);
  const older = items.nth(1);
  await expect(older).toContainText("Cannot complete: Arrange an escort");
  await expect(older).not.toContainText("Urgent");
  await expect(older).not.toHaveClass(/border-l-urgent/);
  await expectAccessible(page);

  // "Urgent only" keeps just the urgent one.
  await page.getByRole("button", { name: "Urgent only" }).click();
  await expect(items).toHaveCount(1);
  await page.getByRole("button", { name: "Urgent only" }).click();
  await expect(items).toHaveCount(2);

  // Opening it marks it read and shows the patient's prep timeline.
  await newest.click();
  await expect(page).toHaveURL(/tab=timeline/);
  const sheet = page.getByRole("dialog", { name: "Sunita Test" });
  await expect(
    sheet.getByRole("tab", { name: "Prep timeline" }),
  ).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(bell).toHaveAccessibleName("Notifications, 1 unread");
  await expect(row).not.toContainText("Unread urgent");

  // The nurse inbox lists the critical-step problem newest first, marked urgent.
  await page.goto("/dashboard/inbox");
  const escalation = page
    .getByRole("list", { name: "Escalations, newest first" })
    .getByRole("listitem")
    .first();
  await expect(escalation).toContainText("Sunita Test");
  await expect(escalation).toContainText("Urgent");
  await expect(escalation).toContainText(RAISED_AT);
  await expectAccessible(page);
  await staff.close();
});
