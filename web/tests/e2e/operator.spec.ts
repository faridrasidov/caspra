import { expect, test, type Page, type Route } from "@playwright/test";

const transaction = {
  id: "65f90e58-a7ef-42df-a082-abc5e55d3050",
  tenant_id: "2999d665-f25b-4c0d-bbeb-63a4c3eef7f6",
  idempotency_key: "a48c9032-10bf-4ee2-8609-cf2fc0b99010",
  type: "debit",
  amount_minor: 2000,
  currency: "USD",
  status: "posted",
  wallet_id: "b55a6fb5-33f4-4271-9902-55963226fafa",
  customer_id: "8956e2e7-b49d-413f-9a9c-1714393af2a4",
  device_id: "9b351f81-59fc-45ec-bcfd-17402af67b34",
  created_at: "2026-07-30T10:13:21Z",
};

const permissions = [
  "customers:read",
  "customers:write",
  "cards:read",
  "cards:write",
  "wallets:read",
  "wallets:adjust",
  "transactions:read",
  "transactions:refund",
  "devices:read",
  "devices:manage",
  "integrations:manage",
  "audit:read",
  "settings:manage",
];

async function mockApi(page: Page) {
  await page.route("**/admin/api/v1/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (path.endsWith("/auth/refresh")) {
      return json(
        {
          type: "https://caspra.dev/problems/unauthorized",
          code: "unauthorized",
          detail: "No session",
        },
        401,
      );
    }
    if (path.endsWith("/auth/login")) {
      return json({
        access_token: "access-token",
        refresh_token: "refresh-token",
        token_type: "bearer",
      });
    }
    if (path.endsWith("/auth/me")) {
      return json({
        id: "57ea44f2-c29b-4fcb-b53d-8f47a071805d",
        tenant_id: transaction.tenant_id,
        email: "operator@caspra.test",
        full_name: "Finance Operator",
        status: "active",
      });
    }
    if (path.endsWith("/auth/permissions")) {
      return json({ permissions });
    }
    if (path.endsWith("/transactions/stats")) {
      return json({
        total_count: 1,
        total_credit_minor: 0,
        total_debit_minor: 2000,
        currency: "USD",
      });
    }
    if (path.endsWith("/transactions/export")) {
      return json({ format: "json", rows: [transaction] });
    }
    if (path.endsWith("/transactions") && method === "GET") {
      return json({ items: [transaction], total: 1, page: 1, limit: 100 });
    }
    if (path.includes("/transactions/") && method === "GET") {
      return json(transaction);
    }
    if (path.endsWith("/refund") && method === "POST") {
      return json(
        {
          id: crypto.randomUUID(),
          tenant_id: transaction.tenant_id,
          original_transaction_id: transaction.id,
          amount_minor: 2000,
          currency: "USD",
          reason: "Customer request",
          status: "completed",
        },
        201,
      );
    }
    if (path.endsWith("/wallets") && method === "GET") {
      return json({
        items: [
          {
            id: transaction.wallet_id,
            tenant_id: transaction.tenant_id,
            customer_id: transaction.customer_id,
            type: "credit",
            currency: "USD",
            balance_minor: 12543068,
            status: "active",
          },
        ],
        total: 1,
        page: 1,
        limit: 100,
      });
    }
    if (path.endsWith("/wallets") && method === "POST") {
      return json(
        {
          id: crypto.randomUUID(),
          tenant_id: transaction.tenant_id,
          customer_id: transaction.customer_id,
          type: "credit",
          currency: "USD",
          balance_minor: 0,
          status: "active",
        },
        201,
      );
    }
    if (path.endsWith("/wallets/transfer") && method === "POST") {
      return json({ ...transaction, type: "transfer" }, 201);
    }
    if (path.endsWith("/topup") && method === "POST") {
      return json({ ...transaction, type: "credit", amount_minor: 1000 }, 201);
    }
    if (path.endsWith("/deduct") && method === "POST") {
      return json({ ...transaction, type: "debit", amount_minor: 500 }, 201);
    }
    if (path.endsWith("/devices") && method === "GET") {
      return json({
        items: [
          {
            id: transaction.device_id,
            tenant_id: transaction.tenant_id,
            name: "POS 01",
            serial: "POS-01",
            type: "reader",
            status: "active",
          },
        ],
        total: 1,
        page: 1,
        limit: 8,
      });
    }
    if (path.endsWith("/reports/daily")) {
      return json({
        currency: "USD",
        rows: [
          {
            day: "2026-07-30",
            transaction_count: 1,
            total_credit_minor: 4831520,
            total_debit_minor: 3681244,
          },
        ],
      });
    }
    if (path.endsWith("/ledger/reconciliation")) {
      return json({
        healthy: true,
        generated_at: "2026-07-30T10:15:00Z",
        checked_transactions: 1,
        checked_wallets: 1,
        issues: [],
      });
    }
    if (path.endsWith("/offline/review")) return json([]);
    if (path.endsWith("/offline/policy")) {
      return json({
        id: crypto.randomUUID(),
        tenant_id: transaction.tenant_id,
        enabled: false,
        uid_risk_accepted: false,
        max_transaction_minor: 0,
        max_card_total_minor: 0,
        max_device_total_minor: 0,
        max_outage_total_minor: 0,
        max_queue_age_seconds: 3600,
        max_queue_size: 100,
        sync_interval_seconds: 60,
      });
    }
    if (path.endsWith("/webhooks/deliveries")) {
      return json({ items: [], total: 0, page: 1, limit: 100 });
    }
    if (path.endsWith("/webhooks")) {
      return json({ items: [], total: 0, page: 1, limit: 100 });
    }
    if (path.endsWith("/customers") && method === "GET") {
      return json({
        items: [
          {
            id: transaction.customer_id,
            tenant_id: transaction.tenant_id,
            full_name: "Ada Lovelace",
            email: "ada@caspra.test",
            phone: null,
            external_id: "ada-1",
            status: "active",
          },
        ],
        total: 1,
        page: 1,
        limit: 100,
      });
    }
    if (path.endsWith("/customers") && method === "POST") {
      return json(
        {
          id: crypto.randomUUID(),
          tenant_id: transaction.tenant_id,
          full_name: "New Customer",
          email: "new@caspra.test",
          status: "active",
        },
        201,
      );
    }
    if (path.endsWith("/customers/import") && method === "POST") {
      return json({ created: 1, skipped: 0 });
    }
    if (path.endsWith("/balances") && method === "GET") {
      return json({
        customer_id: transaction.customer_id,
        balances: [
          {
            wallet_id: transaction.wallet_id,
            currency: "USD",
            balance_minor: 12543068,
            type: "credit",
          },
        ],
      });
    }
    if (path.includes("/customers/") && method === "PATCH") {
      return json({
        id: transaction.customer_id,
        tenant_id: transaction.tenant_id,
        full_name: "Ada Lovelace",
        email: "ada@caspra.test",
        status: "active",
      });
    }
    if (path.includes("/customers/") && method === "DELETE") {
      return json({}, 204);
    }
    if (path.endsWith("/cards") && method === "GET") {
      return json({
        items: [
          {
            id: "3c0f1d7a-2b61-4c0c-9d4b-0a7c6f2e91aa",
            tenant_id: transaction.tenant_id,
            uid: "CARD-001",
            type: "rfid",
            customer_id: transaction.customer_id,
            status: "active",
          },
        ],
        total: 1,
        page: 1,
        limit: 20,
      });
    }
    if (path.endsWith("/cards") && method === "POST") {
      return json(
        {
          id: crypto.randomUUID(),
          tenant_id: transaction.tenant_id,
          uid: "CARD-100",
          type: "rfid",
          status: "active",
        },
        201,
      );
    }
    if (path.includes("/cards/") && method === "POST") {
      return json({
        id: "3c0f1d7a-2b61-4c0c-9d4b-0a7c6f2e91aa",
        tenant_id: transaction.tenant_id,
        uid: "CARD-001",
        type: "rfid",
        customer_id: transaction.customer_id,
        status: path.endsWith("/block") ? "blocked" : "active",
      });
    }
    return json({ items: [], total: 0, page: 1, limit: 100 });
  });
}

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Email").fill("operator@caspra.test");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Wallet liability")).toBeVisible();
}

async function navigateTo(page: Page, destination: string) {
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("link", { name: destination }).click();
}

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
