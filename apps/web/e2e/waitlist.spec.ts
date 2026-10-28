import { expect, test } from "@playwright/test";

const BASE = "http://localhost:3000";

function staffLogin(): { email: string; password: string } {
  const links = JSON.parse(process.env.E2E_LINKS ?? "{}") as Record<
    string,
    string
  >;
  return {
    email: links.staff_email ?? "",
    password: links.staff_password ?? "",
  };
}

function isoDay(daysAhead: number): string {
  return new Date(Date.now() + daysAhead * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
}

test("a coordinator adds a patient to the waitlist and sees them waiting", async ({
  browser,
}) => {
  const staff = await browser.newContext();
  const page = await staff.newPage();
  const { email, password } = staffLogin();

  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard$/);

  // Next navigates on the client; do not wait for a full page load after the click.
  await page
    .getByRole("link", { name: "Waitlist" })
    .click({ noWaitAfter: true });
  await expect(page.getByRole("heading", { name: "Waitlist" })).toBeVisible();

  await page
    .getByLabel("Patient", { exact: true })
    .selectOption({ label: "Asha Test" });
  await page.getByLabel("Can come in from", { exact: true }).fill(isoDay(2));
  await page.getByLabel("Until", { exact: true }).fill(isoDay(4));
  await page.getByRole("button", { name: "Add to waitlist" }).click();

  await expect(page.getByText("Patient added to the waitlist.")).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "Asha Test" }).first(),
  ).toBeVisible();
  await staff.close();
});
