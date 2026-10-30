import { expect, type Page, test } from "@playwright/test";

const BASE = "http://localhost:3000";

type Fixture = Record<string, string>;

function fixture(): Fixture {
  return JSON.parse(process.env.E2E_LINKS ?? "{}") as Fixture;
}

async function signIn(page: Page): Promise<void> {
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(fixture().staff_email ?? "");
  await page.getByLabel("Password").fill(fixture().staff_password ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/dashboard$/);
}

test("a coordinator opens a patient from the overview, reads the prep timeline and logs a call", async ({
  browser,
}) => {
  const staff = await browser.newContext();
  const page = await staff.newPage();
  await signIn(page);

  await expect(
    page.getByRole("heading", { level: 1, name: "Overview" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Next 72 hours" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Filter procedures" }),
  ).toBeVisible();

  // Next navigates on the client; do not wait for a full page load after the click.
  await page
    .getByRole("link", { name: "Open Asha Test" })
    .click({ noWaitAfter: true });
  const sheet = page.getByRole("dialog", { name: "Asha Test" });
  await expect(sheet).toBeVisible();
  await expect(page).toHaveURL(/appointment=/);

  await sheet.getByRole("tab", { name: "Prep timeline" }).click();
  await expect(
    sheet
      .getByRole("list", { name: "Prep steps" })
      .getByText("Clear liquids only")
      .first(),
  ).toBeVisible();

  await sheet.getByRole("button", { name: "Call logged" }).click();
  const confirm = page.getByRole("dialog", {
    name: "Log a call with Asha Test?",
  });
  await confirm.getByRole("button", { name: "Log call" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Call logged" }),
  ).toBeVisible();

  await page.goto(`${BASE}/dashboard/tasks`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Task queue" }),
  ).toBeVisible();
  await page.goto(`${BASE}/dashboard/requests`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Requests" }),
  ).toBeVisible();
  await staff.close();
});

test("a message from the care team reaches the patient's Updates", async ({
  browser,
}) => {
  const staff = await browser.newContext();
  const page = await staff.newPage();
  await signIn(page);

  await page
    .getByRole("link", { name: "Open Neha Test" })
    .click({ noWaitAfter: true });
  const sheet = page.getByRole("dialog", { name: "Neha Test" });
  await sheet.getByRole("tab", { name: "Messages" }).click();
  await sheet
    .getByRole("textbox", { name: "Message the patient" })
    .fill("Please bring your medicine list on the day.");
  await sheet.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByText("Message sent. The patient sees it under Updates."),
  ).toBeVisible();
  await staff.close();

  const patient = await browser.newContext();
  const portal = await patient.newPage();
  const url = new URL(fixture().message ?? "");
  await portal.goto(`${url.pathname}${url.hash}`);
  await portal.waitForURL(/\/p\/home$/);
  await portal
    .getByRole("navigation", { name: "Sections" })
    .getByRole("link", { name: /^Updates/ })
    .click();
  await portal
    .getByRole("button", { name: /Message from your care team/ })
    .click();
  await expect(
    portal
      .getByRole("dialog", { name: "Message from your care team" })
      .getByText("Please bring your medicine list on the day."),
  ).toBeVisible();
  await patient.close();
});
