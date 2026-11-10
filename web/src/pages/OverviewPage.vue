<script setup lang="ts">
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { apiRequest, type Schemas, type TransactionOut } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { formatMoney, formatTime, currencyExponent } from "../utils/format";
import DataState from "../components/DataState.vue";
import PageHeader from "../components/PageHeader.vue";
import OverviewChart from "../components/OverviewChart.vue";
import TransactionTable from "../components/TransactionTable.vue";
import RefundDrawer from "../components/RefundDrawer.vue";
import UiButton from "../components/UiButton.vue";

const { permissions } = useAuth();
const selectedCurrency = ref("");
const start = ref("");
const end = ref("");
const overview = useQuery({
  queryKey: computed(() => ["overview", start.value, end.value]),
  queryFn: () => apiRequest<Schemas["OverviewOut"]>(`/admin/api/v1/overview?${new URLSearchParams({ ...(start.value ? { start: start.value } : {}), ...(end.value ? { end: end.value } : {}) })}`),
  refetchInterval: 15000,
});
const transactions = useQuery({ queryKey: ["transactions", "overview"], queryFn: () => apiRequest<Schemas["PaginatedTransactionOut"]>("/admin/api/v1/transactions?page=1&limit=10"), enabled: computed(() => permissions.value.has("transactions:read")), refetchInterval: 15000 });
const currency = computed(() => selectedCurrency.value || overview.data.value?.currencies[0]?.currency || "USD");
const selected = computed(() => overview.data.value?.currencies.find(row => row.currency === currency.value));
const today = computed(() => overview.data.value?.today.find(row => row.currency === currency.value));
const chart = computed(() => (overview.data.value?.daily ?? []).filter(row => row.currency === currency.value).map(row => ({ day: row.day, load: row.topup_minor / 10 ** currencyExponent(currency.value), spend: row.spend_minor / 10 ** currencyExponent(currency.value) })));
const refundTransaction = ref<TransactionOut | null>(null);
const reconciliationText = computed(() => ({ healthy: "Balanced", unhealthy: "Review required", stale: "Check is stale", not_checked: "Not checked" })[overview.data.value?.reconciliation_state ?? "not_checked"]);
</script>

<template>
  <div>
    <PageHeader title="Operations overview" description="Venue activity and tenant-wide stored-value balances, separated by currency.">
      <template #actions><UiButton variant="secondary" @click="overview.refetch()">Refresh overview</UiButton></template>
    </PageHeader>
    <div class="mb-4 flex flex-wrap gap-4 rounded border border-line bg-white p-3 text-xs">
      <label class="grid gap-1">Currency<select v-model="selectedCurrency" class="rounded border border-line p-2"><option value="">Venue currencies</option><option v-for="row in overview.data.value?.currencies" :key="row.currency" :value="row.currency">{{ row.currency }}</option></select></label>
      <label class="grid gap-1">From<input v-model="start" type="date" class="rounded border border-line p-2" /></label>
      <label class="grid gap-1">Through<input v-model="end" type="date" class="rounded border border-line p-2" /></label>
      <p class="self-end pb-2 text-muted">{{ overview.data.value?.timezone ?? 'Venue timezone' }}</p>
    </div>
    <DataState v-if="overview.isLoading.value" message="Loading operations overview" />
    <DataState v-else-if="overview.error.value" kind="error" :message="overview.error.value.message" retry @retry="overview.refetch()" />
    <div v-else-if="overview.data.value" class="grid gap-4">
      <p v-if="overview.data.value.financial_writes_paused" role="alert" class="rounded border border-danger bg-white p-4 text-sm text-danger">Financial writes are paused. The owner must review reconciliation, repair any differences, and reopen writes from Operational alerts.</p>
      <section class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Financial status">
        <article class="rounded border border-line bg-white p-4"><p class="text-xs text-muted">Wallet liability · paid credit</p><strong class="my-2 block text-xl">{{ formatMoney(selected?.paid_balance_minor ?? 0, currency) }}</strong><p class="text-xs text-muted">Bonus credit {{ formatMoney(selected?.bonus_balance_minor ?? 0, currency) }}</p></article>
        <article class="rounded border border-line bg-white p-4"><p class="text-xs text-muted">Today's load</p><strong class="my-2 block text-xl">{{ formatMoney(today?.topup_minor ?? 0, currency) }}</strong><p class="text-xs text-muted">Confirmed paid credit</p></article>
        <article class="rounded border border-line bg-white p-4"><p class="text-xs text-muted">Today's spend</p><strong class="my-2 block text-xl">{{ formatMoney(today?.spend_minor ?? 0, currency) }}</strong><p class="text-xs text-muted">Refunds {{ formatMoney(today?.refund_minor ?? 0, currency) }}</p></article>
        <article class="rounded border border-line bg-white p-4"><p class="text-xs text-muted">Reconciliation</p><strong class="my-2 block text-xl" :class="overview.data.value.reconciliation_state === 'healthy' ? 'text-success' : 'text-warning'">{{ reconciliationText }}</strong><p class="text-xs text-muted">{{ overview.data.value.reconciliation?.generated_at ? formatTime(String(overview.data.value.reconciliation.generated_at)) : 'Awaiting a completed check' }}</p></article>
      </section>
      <div class="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <section class="rounded border border-line bg-white"><h2 class="border-b border-line p-4 text-sm font-bold">Transaction volume · {{ currency }}</h2><div class="h-[300px] p-4"><OverviewChart :rows="chart" :currency="currency" /></div></section>
        <section class="rounded border border-line bg-white p-4"><h2 class="mb-4 text-sm font-bold">Operational exceptions</h2><dl class="grid gap-4 text-sm"><div class="flex justify-between"><dt>Machine plays needing review</dt><dd>{{ overview.data.value.exceptions.plays ?? 0 }}</dd></div><div class="flex justify-between"><dt>Offline review</dt><dd>{{ overview.data.value.exceptions.offline ?? 0 }}</dd></div><div class="flex justify-between"><dt>Failed webhooks</dt><dd>{{ overview.data.value.exceptions.webhooks ?? 0 }}</dd></div></dl><RouterLink v-if="permissions.has('alerts:read')" class="mt-6 inline-block text-xs text-primary underline" to="/alerts">Open operational alerts</RouterLink></section>
      </div>
      <section class="rounded border border-line bg-white p-4"><h2 class="mb-3 text-sm font-bold">Device health</h2><div class="flex flex-wrap gap-6 text-sm"><span v-for="(count, state) in overview.data.value.device_counts" :key="state"><strong>{{ count }}</strong> {{ state }}</span></div></section>
      <section v-if="permissions.has('transactions:read')" class="overflow-hidden rounded border border-line bg-white"><h2 class="border-b border-line p-4 text-sm font-bold">Recent transactions</h2><DataState v-if="transactions.error.value" kind="error" :message="transactions.error.value.message" /><TransactionTable v-else :transactions="transactions.data.value?.items ?? []" :refundable="permissions.has('transactions:refund')" @refund="refundTransaction = $event" /></section>
    </div>
    <RefundDrawer :transaction="refundTransaction" @close="refundTransaction = null" />
  </div>
</template>
