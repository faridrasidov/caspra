<script setup lang="ts">
import { RiDownloadLine, RiFilter3Line } from "@remixicon/vue";
import { useQuery } from "@tanstack/vue-query";
import { computed, ref } from "vue";

import {
  exportTransactions,
  getTransaction,
  getTransactionStats,
  listTransactions,
  type TransactionOut,
} from "../api/admin";
import AppDrawer from "../components/AppDrawer.vue";
import DataState from "../components/DataState.vue";
import EntityPicker from "../components/EntityPicker.vue";
import PageHeader from "../components/PageHeader.vue";
import RefundDrawer from "../components/RefundDrawer.vue";
import SearchField from "../components/SearchField.vue";
import TransactionTable from "../components/TransactionTable.vue";
import UiButton from "../components/UiButton.vue";
import { downloadJson, formatMoney, formatTime } from "../utils/format";

const search = ref("");
const statusFilter = ref("");
const typeFilter = ref("");
const customerId = ref("");
const walletId = ref("");
const refundTransaction = ref<TransactionOut | null>(null);
const selectedId = ref<string | null>(null);
const exporting = ref(false);
const exportError = ref("");

const stats = useQuery({
  queryKey: ["transaction-stats"],
  queryFn: getTransactionStats,
});

const transactions = useQuery({
  queryKey: computed(() => [
    "transactions",
    typeFilter.value,
    customerId.value,
    walletId.value,
  ]),
  queryFn: () =>
    listTransactions({
      page: 1,
      limit: 100,
      type: typeFilter.value || undefined,
      customer_id: customerId.value || undefined,
      wallet_id: walletId.value || undefined,
    }),
});

const detail = useQuery({
  queryKey: computed(() => ["transaction", selectedId.value]),
  queryFn: () => getTransaction(selectedId.value!),
  enabled: computed(() => Boolean(selectedId.value)),
});

const rows = computed(() => {
  const term = search.value.trim().toLowerCase();
  return (transactions.data.value?.items ?? []).filter(
    (transaction) =>
      (!statusFilter.value || transaction.status === statusFilter.value) &&
      (!term || JSON.stringify(transaction).toLowerCase().includes(term)),
  );
});

function customerLabel(item: Record<string, unknown>) {
  return String(item.full_name || item.email || item.external_id || item.id);
}

function walletLabel(item: Record<string, unknown>) {
  return `${String(item.id).slice(0, 8)} · ${item.currency} · ${item.type}`;
}

async function downloadExport() {
  exportError.value = "";
  exporting.value = true;
  try {
    const payload = await exportTransactions("json");
    downloadJson(`caspra-transactions-${new Date().toISOString().slice(0, 10)}.json`, payload);
  } catch (caught) {
    exportError.value = caught instanceof Error ? caught.message : "Export failed";
  } finally {
    exporting.value = false;
  }
}
</script>

<template>
  <div>
    <PageHeader
      title="Transactions"
      description="Posted ledger activity, captures, and compensating refunds."
    >
      <template #actions>
        <UiButton
          :icon="RiDownloadLine"
          variant="secondary"
          :disabled="exporting"
          @click="downloadExport"
        >
          {{ exporting ? "Exporting..." : "Export" }}
        </UiButton>
      </template>
    </PageHeader>
    <p v-if="exportError" class="mb-3 text-[12px] text-danger" role="alert">{{ exportError }}</p>

    <section
      class="mb-3 grid grid-cols-3 overflow-hidden rounded-md border border-line bg-white max-[760px]:grid-cols-1"
      aria-label="Transaction totals"
    >
      <div class="border-r border-line px-4 py-3 max-[760px]:border-r-0 max-[760px]:border-b">
        <small class="text-[11px] text-muted">Posted count</small>
        <strong class="block text-lg">{{ stats.data.value?.total_count ?? "—" }}</strong>
      </div>
      <div class="border-r border-line px-4 py-3 max-[760px]:border-r-0 max-[760px]:border-b">
        <small class="text-[11px] text-muted">Credit volume</small>
        <strong class="block text-lg">{{
          formatMoney(stats.data.value?.total_credit_minor ?? 0, stats.data.value?.currency ?? "USD")
        }}</strong>
      </div>
      <div class="px-4 py-3">
        <small class="text-[11px] text-muted">Debit volume</small>
        <strong class="block text-lg">{{
          formatMoney(stats.data.value?.total_debit_minor ?? 0, stats.data.value?.currency ?? "USD")
        }}</strong>
      </div>
    </section>

    <section class="overflow-hidden rounded-md border border-line bg-white">
      <div class="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-line p-2.5">
        <SearchField v-model="search" placeholder="Search transactions" />
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-muted focus-within:border-primary">
            <RiFilter3Line aria-hidden="true" class="size-4" />
            <span class="sr-only">Status filter</span>
            <select v-model="statusFilter" class="border-0 bg-transparent text-[12px] text-ink outline-none">
              <option value="">All statuses</option>
              <option value="posted">Posted</option>
              <option value="pending">Pending</option>
              <option value="reversed">Reversed</option>
              <option value="failed">Failed</option>
            </select>
          </label>
          <label class="flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-muted focus-within:border-primary">
            <span class="sr-only">Type filter</span>
            <select v-model="typeFilter" class="border-0 bg-transparent text-[12px] text-ink outline-none">
              <option value="">All types</option>
              <option value="credit">Credit</option>
              <option value="debit">Debit</option>
              <option value="refund">Refund</option>
              <option value="transfer">Transfer</option>
              <option value="preauth">Preauth</option>
              <option value="capture">Capture</option>
              <option value="void">Void</option>
              <option value="adjustment">Adjustment</option>
            </select>
          </label>
        </div>
      </div>
      <div class="grid gap-3 border-b border-line p-2.5 md:grid-cols-2">
        <EntityPicker
          v-model="customerId"
          label="Customer"
          endpoint="/admin/api/v1/customers"
          allow-empty
          empty-label="All customers"
          :option-label="customerLabel"
        />
        <EntityPicker
          v-model="walletId"
          label="Wallet"
          endpoint="/admin/api/v1/wallets"
          allow-empty
          empty-label="All wallets"
          :option-label="walletLabel"
        />
      </div>
      <DataState v-if="transactions.isLoading.value" />
      <DataState
        v-else-if="transactions.error.value"
        kind="error"
        :message="transactions.error.value.message"
        retry
        @retry="transactions.refetch()"
      />
      <TransactionTable
        v-else
        :transactions="rows"
        refundable
        @refund="refundTransaction = $event"
        @select="selectedId = $event.id"
      />
    </section>
    <RefundDrawer :transaction="refundTransaction" @close="refundTransaction = null" />
    <AppDrawer title="Transaction" :open="Boolean(selectedId)" @close="selectedId = null">
      <DataState v-if="detail.isLoading.value" />
      <DataState
        v-else-if="detail.error.value"
        kind="error"
        :message="detail.error.value.message"
        retry
        @retry="detail.refetch()"
      />
      <dl v-else-if="detail.data.value" class="grid gap-3 p-5 text-[12px]">
        <div>
          <dt class="text-[10px] text-muted">Reference</dt>
          <dd class="font-mono text-[11px]">{{ detail.data.value.id }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Time</dt>
          <dd>{{ formatTime(detail.data.value.created_at) }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Type</dt>
          <dd class="capitalize">{{ detail.data.value.type }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Status</dt>
          <dd class="capitalize">{{ detail.data.value.status }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Amount</dt>
          <dd>{{ formatMoney(detail.data.value.amount_minor, detail.data.value.currency) }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Wallet</dt>
          <dd class="font-mono text-[11px]">{{ detail.data.value.wallet_id ?? "-" }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Customer</dt>
          <dd class="font-mono text-[11px]">{{ detail.data.value.customer_id ?? "-" }}</dd>
        </div>
        <div>
          <dt class="text-[10px] text-muted">Description</dt>
          <dd>{{ detail.data.value.description ?? "-" }}</dd>
        </div>
      </dl>
    </AppDrawer>
  </div>
</template>
