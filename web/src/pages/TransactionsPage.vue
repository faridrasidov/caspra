<script setup lang="ts">
import { RiDownloadLine, RiFilter3Line } from "@remixicon/vue";
import { useMutation, useQuery } from "@tanstack/vue-query";
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { apiRequest, downloadExport, type TransactionOut } from "../api/client";
import { useAuth } from "../auth/useAuth";
import DataState from "../components/DataState.vue";
import PageHeader from "../components/PageHeader.vue";
import RefundDrawer from "../components/RefundDrawer.vue";
import SearchField from "../components/SearchField.vue";
import TransactionTable from "../components/TransactionTable.vue";
import UiButton from "../components/UiButton.vue";

const { permissions } = useAuth();
const route = useRoute();
const search = ref("");
const serverSearch = ref("");
const statusFilter = ref("");
const cursor = ref("");
const previousCursors = ref<string[]>([]);
const refundTransaction = ref<TransactionOut | null>(null);
let debounce: ReturnType<typeof setTimeout>;
watch(search, value => { clearTimeout(debounce); debounce = setTimeout(() => { serverSearch.value = value; }, 250); });
watch([serverSearch, statusFilter], () => { cursor.value = ""; previousCursors.value = []; });
const filters = computed(() => ({ ...(serverSearch.value ? { q: serverSearch.value } : {}), ...(statusFilter.value ? { status: statusFilter.value } : {}), ...(route.query.customer_id ? { customer_id: String(route.query.customer_id) } : {}) }));
type History = { items: TransactionOut[]; total: number; next_cursor?: string | null };
const transactions = useQuery({ queryKey: computed(() => ["transactions", filters.value, cursor.value]), queryFn: () => apiRequest<History>(`/admin/api/v1/transactions/history?${new URLSearchParams({ ...filters.value, limit: '20', ...(cursor.value ? { cursor: cursor.value } : {}) })}`) });
const rows = computed(() => transactions.data.value?.items ?? []);
function next() { if (!transactions.data.value?.next_cursor) return; previousCursors.value.push(cursor.value); cursor.value = transactions.data.value.next_cursor; }
function previous() { cursor.value = previousCursors.value.pop() ?? ""; }
const exportId = ref("");
const exportKey = ref(crypto.randomUUID());
type ExportJob = { id: string; status: string; row_count: number; truncated: boolean; error?: string | null };
const exportJob = useQuery({ queryKey: computed(() => ["export", exportId.value]), queryFn: () => apiRequest<ExportJob>(`/admin/api/v1/exports/${exportId.value}`), enabled: computed(() => Boolean(exportId.value)), refetchInterval: query => ['pending', 'processing'].includes(query.state.data?.status ?? 'pending') ? 1000 : false });
const exportMutation = useMutation({ mutationFn: () => apiRequest<ExportJob>("/admin/api/v1/exports", { method: "POST", body: JSON.stringify({ filters: filters.value, format: "csv", idempotency_key: exportKey.value }) }), onSuccess: data => { exportId.value = data.id; } });
const download = useMutation({ mutationFn: async () => { const blob = await downloadExport(`/admin/api/v1/exports/${exportId.value}/download`); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'transactions.csv'; link.click(); URL.revokeObjectURL(url); exportKey.value = crypto.randomUUID(); } });
function exportTransactions() { exportMutation.mutate(); }
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
    <div v-if="exportId" class="mb-4 flex flex-wrap items-center gap-3 rounded border border-line bg-white p-3 text-sm" role="status">
      <span>Export {{ exportJob.data.value?.status ?? 'pending' }} · {{ exportJob.data.value?.row_count ?? 0 }} rows</span>
      <span v-if="exportJob.data.value?.truncated" class="text-warning">Row limit reached. Narrow your filters for the remainder.</span>
      <UiButton v-if="exportJob.data.value?.status === 'completed'" variant="secondary" :disabled="download.isPending.value" @click="download.mutate()">Download CSV</UiButton>
      <span v-if="exportJob.data.value?.error || download.error.value" class="text-danger">{{ exportJob.data.value?.error || download.error.value?.message }}</span>
    </div>
    <p v-if="exportMutation.error.value" role="alert" class="mb-3 text-sm text-danger">{{ exportMutation.error.value.message }}</p>
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
        :refundable="permissions.has('transactions:refund')"
        @refund="refundTransaction = $event"
      />
      <footer class="flex items-center justify-between border-t border-line p-3 text-xs"><UiButton variant="secondary" :disabled="!previousCursors.length" @click="previous">Previous</UiButton><span>{{ transactions.data.value?.total ?? 0 }} matching transactions</span><UiButton variant="secondary" :disabled="!transactions.data.value?.next_cursor" @click="next">Next</UiButton></footer>
    </section>
    <RefundDrawer :transaction="refundTransaction" @close="refundTransaction = null" />
  </div>
</template>
