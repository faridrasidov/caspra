<script setup lang="ts">
import { computed, ref } from "vue";
import { useQuery } from "@tanstack/vue-query";
import { apiRequest, type Schemas } from "../api/client";
import { formatMoney } from "../utils/format";
import PageHeader from "../components/PageHeader.vue";
import DataState from "../components/DataState.vue";

const start = ref("");
const end = ref("");
const currency = ref("");
const reports = useQuery({
  queryKey: computed(() => ["machine-reports", start.value, end.value, currency.value]),
  queryFn: () => apiRequest<Schemas["MachineReportOut"][]>(`/admin/api/v1/reports/machines?${new URLSearchParams({ ...(start.value ? { start: start.value } : {}), ...(end.value ? { end: end.value } : {}), ...(currency.value ? { currency: currency.value } : {}) })}`),
  refetchInterval: 15000,
});
</script>
<template>
  <div>
    <PageHeader title="Machine reports" description="Machine activity and paid revenue after refunds. Default period: the last 14 venue days." />
    <div class="mb-4 flex flex-wrap gap-4 rounded border border-line bg-white p-4 text-sm">
      <label class="grid gap-1">From<input v-model="start" type="date" class="rounded border border-line p-2" /></label>
      <label class="grid gap-1">Through<input v-model="end" type="date" class="rounded border border-line p-2" /></label>
      <label class="grid gap-1">Currency<input v-model="currency" maxlength="3" placeholder="All currencies" class="rounded border border-line p-2 uppercase" @input="currency = currency.toUpperCase()" /></label>
    </div>
    <DataState v-if="reports.isLoading.value" />
    <DataState v-else-if="reports.error.value" kind="error" :message="reports.error.value.message" />
    <DataState v-else-if="!reports.data.value?.length" message="No machines in this period" />
    <section v-else class="overflow-x-auto rounded border border-line bg-white">
      <table class="w-full min-w-[980px] text-left text-xs">
        <thead><tr class="border-b border-line bg-subtle"><th v-for="label in ['Machine', 'Currency', 'Attempts', 'Activated', 'Failed', 'Unresolved', 'Paid spend', 'Bonus spend', 'Refunds', 'Net paid spend', 'Reader offline']" :key="label" class="p-3">{{ label }}</th></tr></thead>
        <tbody><tr v-for="row in reports.data.value" :key="`${row.machine_id}-${row.currency}`" class="border-b border-line"><td class="p-3 font-semibold">{{ row.machine_name }}</td><td class="p-3">{{ row.currency }}</td><td class="p-3">{{ row.attempts }}</td><td class="p-3">{{ row.activations }}</td><td class="p-3">{{ row.failures }}</td><td class="p-3">{{ row.unresolved }}</td><td class="p-3">{{ formatMoney(row.paid_spend_minor, row.currency) }}</td><td class="p-3">{{ formatMoney(row.bonus_spend_minor, row.currency) }}</td><td class="p-3">{{ formatMoney(row.refund_minor, row.currency) }}</td><td class="p-3 font-semibold">{{ formatMoney(row.net_paid_spend_minor, row.currency) }}</td><td class="p-3">{{ Math.round(row.reader_offline_seconds / 60) }} min</td></tr></tbody>
      </table>
    </section>
    <p class="mt-4 text-xs text-muted">Offline time is recorded from heartbeat monitoring after this feature is deployed. Historic downtime before monitoring began is unavailable.</p>
  </div>
</template>
