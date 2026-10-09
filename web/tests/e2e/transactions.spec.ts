import { expect, test, type Page } from "@playwright/test";

import { login, mockApi, navigateTo, transaction } from "./support/mock-api";

const pendingCredit = {
  ...transaction,
  id: "7d8e9f00-1111-4222-8333-444455556666",
  idempotency_key: "11111111-2222-4333-8444-555566667777",
  type: "credit",
  status: "pending",
  amount_minor: 750,
};

async function openTransactions(page: Page) {
  await login(page);
  await navigateTo(page, "Transactions");
  await expect(page.getByText("Posted count")).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.route("**/admin/api/v1/transactions?*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [transaction, pendingCredit],
        total: 2,
        page: 1,
        limit: 100,
      }),
    }),
  );
});

function rowsTable(page: Page) {
  return page.getByRole("main").getByRole("table");
}

test("type filter is sent to the API", async ({ page }) => {
  await openTransactions(page);

  const filtered = page.waitForRequest((r) => {
    const url = new URL(r.url());
    return url.pathname.endsWith("/transactions") && url.searchParams.get("type") === "debit";
  });
  await page.getByLabel("Type filter").selectOption("debit");
  await filtered;
});

test("status filter narrows the visible rows", async ({ page }) => {
  await openTransactions(page);
  await expect(rowsTable(page).getByRole("row")).toHaveCount(3); // header + 2

  await page.getByLabel("Status filter").selectOption("pending");
  await expect(rowsTable(page).getByRole("row")).toHaveCount(2);
  await expect(rowsTable(page)).toContainText("pending");
  await expect(rowsTable(page)).not.toContainText("posted");
});

test("selecting a row loads the transaction detail", async ({ page }) => {
  await openTransactions(page);

  const detail = page.waitForRequest(
    (r) => r.url().endsWith(`/transactions/${transaction.id}`) && r.method() === "GET",
  );
  await rowsTable(page).getByRole("row").nth(1).click();
  await detail;
  await expect(page.getByRole("dialog")).toContainText("Transaction");
});

test("export failure is reported", async ({ page }) => {
  await page.route("**/transactions/export*", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        type: "https://caspra.dev/problems/internal_error",
        code: "internal_error",
        title: "Internal Server Error",
        detail: "An unexpected error occurred",
      }),
    }),
  );
  await openTransactions(page);

  await page.getByRole("button", { name: "Export" }).click();
  await expect(page.getByRole("alert")).toContainText("unexpected error");
});
