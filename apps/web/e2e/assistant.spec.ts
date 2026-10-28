import { expect, test } from "@playwright/test";

const BASE = "http://localhost:3000";

type Fixture = Record<string, string>;

function fixture(): Fixture {
  return JSON.parse(process.env.E2E_LINKS ?? "{}") as Fixture;
}

function portalPath(key: "en" | "hi" | "reuse" | "assist"): string {
  const url = new URL(fixture()[key]);
  return `${url.pathname}${url.hash}`;
}

test("a red-flag question tells the patient to call 112 and reaches the nurse inbox", async ({
  page,
  browser,
}) => {
  await page.goto(portalPath("assist"));
  await expect(page).toHaveURL(/\/p\/home$/);

  await page
    .getByLabel("Your question")
    .fill("I have chest pain since this morning");
  await page.getByRole("button", { name: "Send question" }).click();

  // Next also renders an alert element for route changes, so match the reply itself.
  await expect(
    page.getByRole("alert").filter({ hasText: "112" }),
  ).toBeVisible();

  const staff = await browser.newContext();
  const staffPage = await staff.newPage();
  await staffPage.goto(`${BASE}/login`);
  await staffPage.getByLabel("Email").fill(fixture().staff_email);
  await staffPage.getByLabel("Password").fill(fixture().staff_password);
  await staffPage.getByRole("button", { name: "Sign in" }).click();
  await staffPage.waitForURL(/\/dashboard/);

  await staffPage.goto(`${BASE}/dashboard/inbox`);
  await expect(staffPage.getByText("Urgent").first()).toBeVisible();
  await expect(
    staffPage.getByText(/Red-flag words: CHEST_PAIN/).first(),
  ).toBeVisible();
  await staff.close();
});
