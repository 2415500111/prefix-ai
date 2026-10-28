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

test("a coordinator opens a patient from the next 72 hours and sees the prep steps", async ({
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

  await expect(
    page.getByRole("heading", { name: "Next 72 hours" }),
  ).toBeVisible();
  // Next navigates on the client; do not wait for a full page load after the click.
  await page
    .getByRole("link", { name: "Open Asha Test" })
    .click({ noWaitAfter: true });

  await expect(page.getByRole("heading", { name: "Asha Test" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Prep steps" })).toBeVisible();
  await expect(page.getByText("Clear liquids only").first()).toBeVisible();

  await page.goto(`${BASE}/dashboard/tasks`);
  await expect(page.getByRole("heading", { name: "Task queue" })).toBeVisible();
  await staff.close();
});
