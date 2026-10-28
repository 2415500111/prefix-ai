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

function csvFile(text: string) {
  return {
    name: "patients.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(text),
  };
}

test("a coordinator checks a file, sees the bad row, fixes it and imports", async ({
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

  await page.goto(`${BASE}/dashboard/imports`);
  await expect(
    page.getByRole("heading", { name: "Import records" }),
  ).toBeVisible();
  // The file is read by client code, so wait for it to load before choosing a file.
  await page.waitForLoadState("networkidle");

  await page
    .getByLabel("CSV file")
    .setInputFiles(
      csvFile(
        "first_name,last_name,date_of_birth\nAsha,Imports,1968-03-14\n,Nobody,1980-01-01\n",
      ),
    );
  await page.getByRole("button", { name: "Check file" }).click();

  await expect(page.getByRole("cell", { name: "first_name" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "is required" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Import / })).toHaveCount(0);

  await page
    .getByLabel("CSV file")
    .setInputFiles(
      csvFile("first_name,last_name,date_of_birth\nAsha,Imports,1968-03-14\n"),
    );
  await page.getByRole("button", { name: "Check file" }).click();
  await expect(
    page.getByText(
      "All 1 patient can be imported. Nothing has been saved yet.",
    ),
  ).toBeVisible();

  await page.getByRole("button", { name: "Import 1 patients" }).click();
  await expect(page.getByText("Imported 1 patient.")).toBeVisible();
  await staff.close();
});
