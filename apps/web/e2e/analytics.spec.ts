import { expect, test } from "@playwright/test";

const BASE = "http://localhost:3000";

test("a coordinator sees the analytics figures and can download the procedure list", async ({
  browser,
}) => {
  const links = JSON.parse(process.env.E2E_LINKS ?? "{}") as Record<
    string,
    string
  >;
  const staff = await browser.newContext();
  const page = await staff.newPage();

  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(links.staff_email ?? "");
  await page.getByLabel("Password").fill(links.staff_password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard$/);

  await page.goto(`${BASE}/dashboard/analytics`);
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(
    page.getByText("Cancellation rate", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Not tracked yet")).toBeVisible();
  await expect(page.getByRole("link", { name: "Download CSV" })).toBeVisible();
  await staff.close();
});
