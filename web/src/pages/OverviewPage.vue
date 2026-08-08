<script setup lang="ts">
import {
  RiAlertLine,
  RiCheckboxCircleLine,
  RiDownload2Line,
  RiRefreshLine,
  RiUpload2Line,
  RiWallet3Line,
} from "@remixicon/vue";
import { useQuery } from "@tanstack/vue-query";
import { computed, ref, type Component } from "vue";

import { apiRequest, type Schemas, type TransactionOut } from "../api/client";
import DataState from "../components/DataState.vue";
import IconButton from "../components/IconButton.vue";
import OverviewChart from "../components/OverviewChart.vue";
import RefundDrawer from "../components/RefundDrawer.vue";
import StatusMark from "../components/StatusMark.vue";
import TransactionTable from "../components/TransactionTable.vue";
import { formatMoney, formatTime } from "../utils/format";

type OverviewData = {
  transactions: Schemas["PaginatedTransactionOut"];
  wallets: Schemas["PaginatedWalletOut"];
  devices: Schemas["PaginatedDeviceOut"];
  daily: Schemas["DailyReportOut"];
  reconciliation: Schemas["ReconciliationReportOut"];
  offline: Schemas["OfflineReviewItemOut"][];
  deliveries: Schemas["PaginatedWebhookDeliveryOut"];
};

async function loadOverview(): Promise<OverviewData> {
  const [transactions, wallets, devices, daily, reconciliation, offline, deliveries] =
    await Promise.all([
      apiRequest<Schemas["PaginatedTransactionOut"]>(
        "/admin/api/v1/transactions?page=1&limit=10",
      ),
      apiRequest<Schemas["PaginatedWalletOut"]>(
        "/admin/api/v1/wallets?page=1&limit=100",
      ),
      apiRequest<Schemas["PaginatedDeviceOut"]>(
        "/admin/api/v1/devices?page=1&limit=8",
      ),
      apiRequest<Schemas["DailyReportOut"]>("/admin/api/v1/reports/daily"),
      apiRequest<Schemas["ReconciliationReportOut"]>(
        "/admin/api/v1/ledger/reconciliation",
      ),
      apiRequest<Schemas["OfflineReviewItemOut"][]>("/admin/api/v1/offline/review"),
      apiRequest<Schemas["PaginatedWebhookDeliveryOut"]>(
        "/admin/api/v1/webhooks/deliveries?page=1&limit=5",
      ),
    ]);
  return { transactions, wallets, devices, daily, reconciliation, offline, deliveries };
}

const overview = useQuery({ queryKey: ["overview"], queryFn: loadOverview });
const refundTransaction = ref<TransactionOut | null>(null);
const derived = computed(() => {
  if (!overview.data.value) return null;
  const data = overview.data.value;
  const currency = data.wallets.items[0]?.currency ?? data.daily.currency ?? "USD";
  const liability = data.wallets.items.reduce(
    (total, wallet) => total + wallet.balance_minor,
    0,
  );
  const latestDay = data.daily.rows.at(-1);
  const chart = data.daily.rows.slice(-14).map((row) => ({
    day: new Date(`${row.day}T00:00:00`).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    }),
    load: row.total_credit_minor / 100,
    spend: row.total_debit_minor / 100,
  }));
  return {
    currency,
    liability,
    latestDay,
    chart,
    reconciliationCount: data.reconciliation.issues.length,
  };
});
const failedDeliveries = computed(() =>
  (overview.data.value?.deliveries.items ?? []).filter(
    (delivery) => !["success", "pending"].includes(delivery.status),
  ),
);
const metrics = computed<
  { label: string; value: string; detail: string; icon: Component; tone: string }[]
>(() => {
  if (!overview.data.value || !derived.value) return [];
  return [
    {
      label: "Wallet liability",
      value: formatMoney(derived.value.liability, derived.value.currency),
      detail: `${overview.data.value.wallets.total} active wallet records`,
      icon: RiWallet3Line,
      tone: "text-primary",
    },
    {
      label: "Today's load",
      value: formatMoney(
        derived.value.latestDay?.total_credit_minor ?? 0,
        derived.value.currency,
      ),
      detail: `${derived.value.latestDay?.transaction_count ?? 0} transactions`,
      icon: RiDownload2Line,
      tone: "text-success",
    },
    {
      label: "Today's spend",
      value: formatMoney(
        derived.value.latestDay?.total_debit_minor ?? 0,
        derived.value.currency,
      ),
      detail: "Posted debit volume",
      icon: RiUpload2Line,
      tone: "text-success",
    },
    {
      label: "Reconciliation",
      value: derived.value.reconciliationCount ? "Review required" : "Balanced",
      detail: `${derived.value.reconciliationCount} differences`,
      icon: derived.value.reconciliationCount ? RiAlertLine : RiCheckboxCircleLine,
      tone: derived.value.reconciliationCount ? "text-warning" : "text-success",
    },
  ];
});
</script>

<template>
  <DataState
    v-if="overview.isLoading.value"
    message="Loading operations overview"
  />
  <DataState
    v-else-if="overview.error.value || !overview.data.value || !derived"
    kind="error"
    :message="overview.error.value?.message ?? 'Overview is unavailable'"
    retry
    @retry="overview.refetch()"
  />
  <div v-else>
    <section
      class="-mx-[22px] -mt-[18px] mb-4 grid min-h-[112px] grid-cols-4 border-b border-line bg-white px-[22px] max-[1120px]:grid-cols-2 max-[760px]:-mx-3 max-[760px]:-mt-4 max-[760px]:mb-3 max-[760px]:grid-cols-1 max-[760px]:px-3"
      aria-label="Financial status"
    >
      <div
        v-for="metric in metrics"
        :key="metric.label"
        class="flex min-w-0 items-start justify-between border-r border-line px-5 py-5 first:pl-1 last:border-r-0 max-[1120px]:nth-[2]:border-r-0 max-[1120px]:nth-[-n+2]:border-b max-[760px]:min-h-[88px] max-[760px]:border-r-0 max-[760px]:border-b max-[760px]:px-1 max-[760px]:py-3.5"
      >
        <span class="grid min-w-0 gap-1">
          <small class="text-[11px] text-muted">{{ metric.label }}</small>
          <strong class="truncate text-xl font-bold tracking-[-0.02em] max-[760px]:text-lg">{{ metric.value }}</strong>
          <em class="text-[10px] not-italic text-muted">{{ metric.detail }}</em>
        </span>
        <component :is="metric.icon" aria-hidden="true" class="size-[23px] shrink-0" :class="metric.tone" />
      </div>
    </section>

    <div class="grid grid-cols-[minmax(0,2.2fr)_minmax(280px,.95fr)] gap-3 max-[1120px]:grid-cols-1">
      <section class="h-[342px] overflow-hidden rounded-md border border-line bg-white max-[760px]:h-[300px]">
        <header class="flex min-h-14 items-center justify-between border-b border-line px-3.5 py-2.5">
          <div>
            <h2 class="text-[13px] font-bold">Transaction volume</h2>
            <p class="mt-0.5 text-[10px] text-muted">Daily posted value</p>
          </div>
          <div class="flex gap-4 text-[10px] text-muted">
            <span class="flex items-center gap-1.5 before:h-0.5 before:w-4 before:bg-primary">Load</span>
            <span class="flex items-center gap-1.5 before:h-0.5 before:w-4 before:bg-success">Spend</span>
          </div>
        </header>
        <div class="h-[284px] p-3.5 max-[760px]:h-[236px]">
          <OverviewChart :rows="derived.chart" :currency="derived.currency" />
        </div>
      </section>

      <section class="min-h-[342px] overflow-hidden rounded-md border border-line bg-white max-[1120px]:min-h-0">
        <header class="flex min-h-14 items-center justify-between border-b border-line px-3.5 py-2.5">
          <div>
            <h2 class="text-[13px] font-bold">Operational exceptions</h2>
            <p class="mt-0.5 text-[10px] text-muted">Queues that need attention</p>
          </div>
          <IconButton label="Refresh exceptions" :icon="RiRefreshLine" @click="overview.refetch()" />
        </header>
        <div class="border-b border-line p-3.5">
          <h3 class="mb-3 text-[11px] font-bold">Offline review <span class="ml-1 rounded border border-[#e7b957] bg-warning-soft px-1.5 py-0.5 text-warning">{{ overview.data.value.offline.length }}</span></h3>
          <div v-if="overview.data.value.offline.length" class="grid gap-2">
            <div v-for="item in overview.data.value.offline.slice(0, 3)" :key="item.id" class="flex items-center justify-between gap-2">
              <span class="grid"><strong class="text-[11px]">Sequence {{ item.sequence_number }}</strong><small class="text-[9px] text-muted">{{ formatMoney(item.amount_minor) }} / {{ item.card_uid }}</small></span>
              <StatusMark :value="item.status" />
            </div>
          </div>
          <p v-else class="py-2 text-[10px] text-muted">No items waiting.</p>
        </div>
        <div class="p-3.5">
          <h3 class="mb-3 text-[11px] font-bold">Failed webhooks <span class="ml-1 rounded border border-[#e7b957] bg-warning-soft px-1.5 py-0.5 text-warning">{{ failedDeliveries.length }}</span></h3>
          <div v-if="failedDeliveries.length" class="grid gap-2">
            <div v-for="delivery in failedDeliveries.slice(0, 3)" :key="delivery.id" class="flex items-center justify-between gap-2">
              <span class="grid"><strong class="text-[11px]">{{ delivery.event_type }}</strong><small class="text-[9px] text-muted">{{ delivery.attempts }} attempts / {{ formatTime(delivery.next_retry_at) }}</small></span>
              <StatusMark :value="delivery.status" />
            </div>
          </div>
          <p v-else class="py-2 text-[10px] text-muted">No items waiting.</p>
        </div>
      </section>

      <section class="min-h-[220px] overflow-hidden rounded-md border border-line bg-white max-[760px]:min-h-0">
        <header class="min-h-14 border-b border-line px-3.5 py-2.5">
          <h2 class="text-[13px] font-bold">Recent transactions</h2>
          <p class="mt-0.5 text-[10px] text-muted">Newest posted activity</p>
        </header>
        <TransactionTable
          :transactions="overview.data.value.transactions.items"
          refundable
          @refund="refundTransaction = $event"
        />
      </section>

      <section class="min-h-[220px] overflow-hidden rounded-md border border-line bg-white max-[1120px]:min-h-0">
        <header class="min-h-14 border-b border-line px-3.5 py-2.5">
          <h2 class="text-[13px] font-bold">Device health</h2>
          <p class="mt-0.5 text-[10px] text-muted">Latest registered state</p>
        </header>
        <div>
          <div v-for="device in overview.data.value.devices.items" :key="device.id" class="flex min-h-12 items-center justify-between border-b border-line px-3.5 py-2 last:border-b-0">
            <span class="grid"><strong class="text-[11px]">{{ device.name }}</strong><small class="text-[9px] text-muted">{{ device.type }}</small></span>
            <StatusMark :value="device.status" />
          </div>
        </div>
      </section>
    </div>
    <RefundDrawer :transaction="refundTransaction" @close="refundTransaction = null" />
  </div>
</template>
