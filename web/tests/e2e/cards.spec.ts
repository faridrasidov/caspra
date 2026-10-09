import { expect, test, type Page } from "@playwright/test";

import { login, mockApi, navigateTo, transaction } from "./support/mock-api";

const cardId = "3c0f1d7a-2b61-4c0c-9d4b-0a7c6f2e91aa";

async function openCards(page: Page) {
  await login(page);
  await navigateTo(page, "Cards");
  await expect(page.getByText("CARD-001")).toBeVisible();
}

async function openCardDetail(page: Page) {
  await page.getByText("CARD-001").click();
  await expect(page.getByRole("dialog")).toContainText("UID");
}

test("register sends the UID and optional customer", async ({ page }) => {
  const recorded = await mockApi(page);
  await openCards(page);

  await page.getByRole("button", { name: "Register card" }).click();
  await page.getByLabel("Card UID").fill("CARD-200");
  const done = page.waitForResponse(
    (r) => r.url().endsWith("/cards") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Register card" }).last().click();
  await done;

  const body = recorded.find((r) => r.method === "POST" && r.path.endsWith("/cards"))?.body;
  expect(body).toMatchObject({ uid: "CARD-200" });
  expect((body as { customer_id?: string }).customer_id ?? null).toBeNull();
});

test("block posts to the card's block endpoint", async ({ page }) => {
  await mockApi(page);
  await openCards(page);

  const block = page.waitForRequest(
    (r) => r.url().endsWith(`/cards/${cardId}/block`) && r.method() === "POST",
  );
  await page.getByTitle("Block card", { exact: true }).click();
  await block;
});

test("blocked cards offer unblock instead", async ({ page }) => {
  await mockApi(page);
  await page.route("**/admin/api/v1/cards?*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: cardId,
            tenant_id: transaction.tenant_id,
            uid: "CARD-001",
            type: "rfid",
            customer_id: transaction.customer_id,
            status: "blocked",
          },
        ],
        total: 1,
        page: 1,
        limit: 20,
      }),
    }),
  );
  await openCards(page);

  await expect(page.getByTitle("Block card", { exact: true })).toHaveCount(0);
  const unblock = page.waitForRequest(
    (r) => r.url().endsWith(`/cards/${cardId}/unblock`) && r.method() === "POST",
  );
  await page.getByTitle("Unblock card").click();
  await unblock;
});

test("replace sends the new UID", async ({ page }) => {
  const recorded = await mockApi(page);
  await openCards(page);
  await openCardDetail(page);

  await page.getByRole("button", { name: "Replace", exact: true }).click();
  await page.getByLabel("New card UID").fill("CARD-NEW");
  const done = page.waitForResponse((r) => r.url().endsWith("/replace"));
  await page.getByRole("button", { name: "Replace card" }).click();
  await done;

  const body = recorded.find((r) => r.path.endsWith(`/cards/${cardId}/replace`))?.body;
  expect(body).toEqual({ new_uid: "CARD-NEW" });
});

test("unassign is offered only for assigned cards and posts to unassign", async ({ page }) => {
  await mockApi(page);
  await openCards(page);
  await openCardDetail(page);

  const unassign = page.waitForRequest(
    (r) => r.url().endsWith(`/cards/${cardId}/unassign`) && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Unassign" }).click();
  await unassign;
});
