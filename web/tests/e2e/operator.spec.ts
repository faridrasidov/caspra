import { expect, test } from "@playwright/test";

import { login, mockApi, navigateTo, transaction } from "./support/mock-api";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("operator can sign in, inspect a charge, and submit a refund", async ({
  page,
}, testInfo) => {
  await login(page);
  const screenshotDirectory = process.env.CASPRA_SCREENSHOT_DIR ?? "../docs/design";
  const mobileProject = testInfo.project.name.includes("mobile");
  await page.screenshot({
    path: mobileProject
      ? `${screenshotDirectory}/operator-dashboard-mobile.png`
      : `${screenshotDirectory}/operator-dashboard-implemented.png`,
    fullPage: true,
  });
  await page.getByTitle("Refund transaction").click();
  await expect(page.getByRole("dialog")).toContainText("Refund transaction");
  if (!mobileProject) {
    await page.waitForTimeout(250);
    await page.screenshot({
      path: `${screenshotDirectory}/operator-dashboard-refund.png`,
      fullPage: true,
    });
  }
  await page.getByLabel("Reason required").selectOption("Customer request");
  const refundRequest = page.waitForRequest(
    (request) => request.url().endsWith("/refund") && request.method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm refund" }).click();
  await refundRequest;
});

test("operator can register an assigned card and initiate a wallet top-up", async ({
  page,
}) => {
  await login(page);
  await navigateTo(page, "Cards");
  await page.getByRole("button", { name: "Register card" }).click();
  await page.getByLabel("Card UID").fill("CARD-100");
  await page.getByLabel("Customer").selectOption(transaction.customer_id);
  await page.getByRole("button", { name: "Register card" }).last().click();

  await navigateTo(page, "Wallets");
  await page.getByTitle("Top up wallet").click();
  await page.getByLabel("Amount").fill("10.00");
  await page.getByLabel("Reason required").fill("Cash desk load");
  const topupRequest = page.waitForRequest(
    (request) => request.url().endsWith("/topup") && request.method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm top-up" }).click();
  await topupRequest;
});

test("operator can review customer balances and export transactions", async ({
  page,
}) => {
  await login(page);
  await navigateTo(page, "Customers");
  await page.getByText("Ada Lovelace").click();
  await expect(page.getByRole("dialog")).toContainText("Balances");
  await expect(page.getByRole("dialog")).toContainText("credit");

  await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
  await navigateTo(page, "Transactions");
  await expect(page.getByText("Posted count")).toBeVisible();
  const exportRequest = page.waitForRequest(
    (request) => request.url().includes("/transactions/export") && request.method() === "GET",
  );
  await page.getByRole("button", { name: "Export" }).click();
  await exportRequest;
});
