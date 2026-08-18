import { apiRequest, toQuery, type Schemas } from "./client";

const BASE = "/admin/api/v1";

export type CustomerOut = Schemas["CustomerOut"];
export type CustomerCreate = Schemas["CustomerCreate"];
export type CustomerUpdate = Schemas["CustomerUpdate"];
export type CustomerBalancesOut = Schemas["CustomerBalancesOut"];
export type CustomerImportResult = Schemas["CustomerImportResult"];
export type CardOut = Schemas["CardOut"];
export type WalletOut = Schemas["WalletOut"];
export type WalletType = Schemas["WalletType"];
export type TransactionOut = Schemas["TransactionOut"];
export type TransactionStatsOut = Schemas["TransactionStatsOut"];
export type TransactionExportOut = Schemas["TransactionExportOut"];

export function listCustomers(page = 1, limit = 100) {
  return apiRequest<Schemas["PaginatedCustomerOut"]>(
    `${BASE}/customers${toQuery({ page, limit })}`,
  );
}

export function createCustomer(payload: CustomerCreate) {
  return apiRequest<CustomerOut>(`${BASE}/customers`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCustomer(customerId: string, payload: CustomerUpdate) {
  return apiRequest<CustomerOut>(`${BASE}/customers/${customerId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCustomer(customerId: string) {
  return apiRequest<void>(`${BASE}/customers/${customerId}`, { method: "DELETE" });
}

export function getCustomerBalances(customerId: string) {
  return apiRequest<CustomerBalancesOut>(`${BASE}/customers/${customerId}/balances`);
}

export function importCustomers(customers: CustomerCreate[]) {
  return apiRequest<CustomerImportResult>(`${BASE}/customers/import`, {
    method: "POST",
    body: JSON.stringify({ customers }),
  });
}

export function createCard(payload: { uid: string; type?: Schemas["CardType"]; customer_id?: string | null }) {
  return apiRequest<CardOut>(`${BASE}/cards`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function assignCard(cardId: string, customerId: string) {
  return apiRequest<CardOut>(`${BASE}/cards/${cardId}/assign`, {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId }),
  });
}

export function unassignCard(cardId: string) {
  return apiRequest<CardOut>(`${BASE}/cards/${cardId}/unassign`, { method: "POST" });
}

export function blockCard(cardId: string) {
  return apiRequest<CardOut>(`${BASE}/cards/${cardId}/block`, { method: "POST" });
}

export function unblockCard(cardId: string) {
  return apiRequest<CardOut>(`${BASE}/cards/${cardId}/unblock`, { method: "POST" });
}

export function resetCard(cardId: string) {
  return apiRequest<CardOut>(`${BASE}/cards/${cardId}/reset`, { method: "POST" });
}

export function replaceCard(cardId: string, newUid: string) {
  return apiRequest<CardOut>(`${BASE}/cards/${cardId}/replace`, {
    method: "POST",
    body: JSON.stringify({ new_uid: newUid }),
  });
}

export function listWallets(page = 1, limit = 100) {
  return apiRequest<Schemas["PaginatedWalletOut"]>(
    `${BASE}/wallets${toQuery({ page, limit })}`,
  );
}

export function createWallet(payload: {
  customer_id: string;
  currency: string;
  type?: WalletType;
}) {
  return apiRequest<WalletOut>(`${BASE}/wallets`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function transferWallet(payload: {
  from_wallet_id: string;
  to_wallet_id: string;
  amount_minor: number;
  currency: string;
  description?: string;
}) {
  return apiRequest<TransactionOut>(`${BASE}/wallets/transfer`, {
    method: "POST",
    body: JSON.stringify({ ...payload, idempotency_key: crypto.randomUUID() }),
  });
}

export function topupWallet(
  walletId: string,
  payload: { amount_minor: number; currency: string; description?: string },
) {
  return apiRequest<TransactionOut>(`${BASE}/wallets/${walletId}/topup`, {
    method: "POST",
    body: JSON.stringify({ ...payload, idempotency_key: crypto.randomUUID() }),
  });
}

export function deductWallet(
  walletId: string,
  payload: { amount_minor: number; currency: string; description?: string },
) {
  return apiRequest<TransactionOut>(`${BASE}/wallets/${walletId}/deduct`, {
    method: "POST",
    body: JSON.stringify({ ...payload, idempotency_key: crypto.randomUUID() }),
  });
}

export function listTransactions(filters: {
  page?: number;
  limit?: number;
  type?: string;
  wallet_id?: string;
  customer_id?: string;
} = {}) {
  return apiRequest<Schemas["PaginatedTransactionOut"]>(
    `${BASE}/transactions${toQuery({
      page: filters.page ?? 1,
      limit: filters.limit ?? 100,
      type: filters.type,
      wallet_id: filters.wallet_id,
      customer_id: filters.customer_id,
    })}`,
  );
}

export function getTransaction(transactionId: string) {
  return apiRequest<TransactionOut>(`${BASE}/transactions/${transactionId}`);
}

export function getTransactionStats() {
  return apiRequest<TransactionStatsOut>(`${BASE}/transactions/stats`);
}

export function exportTransactions(format = "json") {
  return apiRequest<TransactionExportOut>(
    `${BASE}/transactions/export${toQuery({ format })}`,
  );
}

export function refundTransaction(
  transactionId: string,
  payload: { amount_minor?: number; reason?: string },
) {
  return apiRequest<Schemas["RefundOut"]>(`${BASE}/transactions/${transactionId}/refund`, {
    method: "POST",
    body: JSON.stringify({ ...payload, idempotency_key: crypto.randomUUID() }),
  });
}
