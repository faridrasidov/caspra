import { expect, test, type Page } from "@playwright/test";

import {
  login,
  mockApi,
  navigateTo,
  type RecordedRequest,
  transaction,
} from "./support/mock-api";

const secondWalletId = "c1d2e3f4-0000-4000-8000-000000000002";

function lastPost(recorded: RecordedRequest[], suffix: string) {
  const match = recorded.filter((r) => r.method === "POST" && r.path.endsWith(suffix)).at(-1);
  expect(match, `expected a POST to ${suffix}`).toBeDefined();
  return match!.body as Record<string, unknown>;
}

async function openWallets(page: Page) {
  await login(page);
  await navigateTo(page, "Wallets");
  await expect(page.getByTitle("Top up wallet")).toBeVisible();
}

test("top-up sends integer minor units and a fresh idempotency key", async ({ page }) => {
  const recorded = await mockApi(page);
  await openWallets(page);

  for (const amount of ["19.99", "0.10"]) {
    await page.getByTitle("Top up wallet").click();
    await page.getByLabel("Amount").fill(amount);
    await page.getByLabel("Reason required").fill("Cash desk load");
    const done = page.waitForResponse((r) => r.url().endsWith("/topup"));
    await page.getByRole("button", { name: "Confirm top-up" }).click();
    await done;
  }

  const topups = recorded.filter((r) => r.method === "POST" && r.path.endsWith("/topup"));
  expect(topups.map((r) => (r.body as { amount_minor: number }).amount_minor)).toEqual([
    1999, 10,
  ]);
  const [first, second] = topups.map((r) => r.body as Record<string, unknown>);
  expect(first).toMatchObject({ currency: "USD", description: "Cash desk load" });
  expect(first.idempotency_key).toEqual(expect.stringMatching(/^[0-9a-f-]{36}$/));
  expect(second.idempotency_key).not.toEqual(first.idempotency_key);
  expect(topups[0].path).toContain(`/wallets/${transaction.wallet_id}/topup`);
});

test("deduct posts to the deduct endpoint and closes the drawer", async ({ page }) => {
  const recorded = await mockApi(page);
  await openWallets(page);

  await page.getByTitle("Deduct wallet").click();
  await expect(page.getByRole("dialog")).toContainText("Deduct wallet");
  await page.getByLabel("Amount").fill("5.00");
  await page.getByLabel("Reason required").fill("Damaged goods");
  const done = page.waitForResponse((r) => r.url().endsWith("/deduct"));
  await page.getByRole("button", { name: "Confirm deduct" }).click();
  await done;

  expect(lastPost(recorded, "/deduct")).toMatchObject({
    amount_minor: 500,
    currency: "USD",
    description: "Damaged goods",
  });
  await expect(page.getByRole("dialog")).toBeHidden();
});

test("top-up requires an amount and a reason", async ({ page }) => {
  const recorded = await mockApi(page);
  await openWallets(page);

  await page.getByTitle("Top up wallet").click();
  await page.getByRole("button", { name: "Confirm top-up" }).click();

  await expect(page.getByRole("dialog")).toBeVisible();
  expect(recorded.some((r) => r.path.endsWith("/topup"))).toBe(false);
});

test("API errors are shown in the drawer", async ({ page }) => {
  await mockApi(page);
  await page.route("**/topup", (route) =>
    route.fulfill({
      status: 402,
      contentType: "application/json",
      body: JSON.stringify({
        type: "https://caspra.dev/problems/insufficient_funds",
        code: "insufficient_funds",
        title: "Payment Required",
        detail: "Insufficient funds",
      }),
    }),
  );
  await openWallets(page);

  await page.getByTitle("Top up wallet").click();
  await page.getByLabel("Amount").fill("1.00");
  await page.getByLabel("Reason required").fill("Test");
  await page.getByRole("button", { name: "Confirm top-up" }).click();

  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("Insufficient funds");
});

test("transfer sends both wallets and the amount", async ({ page }) => {
  const recorded = await mockApi(page);
  await page.route("**/admin/api/v1/wallets?*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: transaction.wallet_id,
            tenant_id: transaction.tenant_id,
            customer_id: transaction.customer_id,
            type: "credit",
            currency: "USD",
            balance_minor: 5000,
            status: "active",
          },
          {
            id: secondWalletId,
            tenant_id: transaction.tenant_id,
            customer_id: transaction.customer_id,
            type: "token",
            currency: "USD",
            balance_minor: 0,
            status: "active",
          },
        ],
        total: 2,
        page: 1,
        limit: 100,
      }),
    }),
  );
  await login(page);
  await navigateTo(page, "Wallets");

  await page.getByRole("button", { name: "Transfer" }).click();
  await page.getByLabel("From wallet").selectOption(transaction.wallet_id);
  await page.getByLabel("To wallet").selectOption(secondWalletId);
  await page.getByLabel("Amount").fill("12.50");
  await page.getByLabel("Reason required").fill("Move to token wallet");
  const done = page.waitForResponse((r) => r.url().endsWith("/wallets/transfer"));
  await page.getByRole("button", { name: "Confirm transfer" }).click();
  await done;

  expect(lastPost(recorded, "/wallets/transfer")).toMatchObject({
    from_wallet_id: transaction.wallet_id,
    to_wallet_id: secondWalletId,
    amount_minor: 1250,
    currency: "USD",
  });
});
