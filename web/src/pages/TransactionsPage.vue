<script setup lang="ts">
import { RiDownloadLine, RiFilter3Line } from "@remixicon/vue";
import { useQuery } from "@tanstack/vue-query";
import { computed, ref } from "vue";

import { apiRequest, type Schemas, type TransactionOut } from "../api/client";
import DataState from "../components/DataState.vue";
import PageHeader from "../components/PageHeader.vue";
import RefundDrawer from "../components/RefundDrawer.vue";
import SearchField from "../components/SearchField.vue";
import TransactionTable from "../components/TransactionTable.vue";
import UiButton from "../components/UiButton.vue";

const search = ref("");
const statusFilter = ref("");
const refundTransaction = ref<TransactionOut | null>(null);
const transactions = useQuery({
  queryKey: ["transactions"],
  queryFn: () =>
    apiRequest<Schemas["PaginatedTransactionOut"]>(
      "/admin/api/v1/transactions?page=1&limit=100",
    ),
});
const rows = computed(() => {
  const term = search.value.trim().toLowerCase();
  return (transactions.data.value?.items ?? []).filter(
    (transaction) =>
      (!statusFilter.value || transaction.status === statusFilter.value) &&
      (!term || JSON.stringify(transaction).toLowerCase().includes(term)),
  );
});

function exportTransactions() {
  window.open("/admin/api/v1/transactions/export", "_blank");
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
          @click="exportTransactions"
        >
          Export
        </UiButton>
      </template>
    </PageHeader>
    <section class="overflow-hidden rounded-md border border-line bg-white">
      <div class="flex min-h-14 items-center justify-between gap-3 border-b border-line p-2.5 max-[760px]:flex-col max-[760px]:items-stretch">
        <SearchField v-model="search" placeholder="Search transactions" />
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
      />
    </section>
    <RefundDrawer :transaction="refundTransaction" @close="refundTransaction = null" />
  </div>
</template>
