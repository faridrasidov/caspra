<script setup lang="ts">
import { computed, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import { resourceOptions } from "../api/options";
import { useAuth } from "../auth/useAuth";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import ResourcePage, { type ResourceColumn, type ResourceRecord } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";
import { formatMoney } from "../utils/format";

const { user, permissions } = useAuth();
const queryClient = useQueryClient();
const mode = ref<"open" | "topup" | "close" | "review" | "movement" | null>(null);
const shift = ref<ResourceRecord | null>(null);
const reviewQueue = ref(false);
const endpoint = computed(() => `/admin/api/v1/shifts${reviewQueue.value ? '/review' : ''}`);
const customers = useQuery({ queryKey: ["customer-options"], queryFn: () => resourceOptions("/admin/api/v1/customers", "full_name") });
const org = useQuery({ queryKey: ["org"], queryFn: () => apiRequest<{ default_currency: string }>("/admin/api/v1/org") });
type Package = { id: string; name: string; currency: string; paid_minor: number; bonus_minor: number; active: boolean };
const packages = useQuery({ queryKey: ["packages"], queryFn: () => apiRequest<{ items: Package[] }>("/admin/api/v1/topup-packages?limit=100") });
const currency = computed(() => String(shift.value?.currency ?? org.data.value?.default_currency ?? "USD"));
const receipt = ref<{ number: string; paid_minor: number; bonus_minor: number; currency: string } | null>(null);
const columns: ResourceColumn[] = [{ key: "terminal", label: "Terminal" }, { key: "opening_minor", label: "Opening", kind: "money" }, { key: "expected_minor", label: "Expected", kind: "money" }, { key: "variance_minor", label: "Variance", kind: "money" }, { key: "closed_at", label: "Closed" }, { key: "review_reason", label: "Manager review" }];
const fields = computed<ActionField[]>(() => {
  if (mode.value === "open") return [{ key: "terminal", label: "Terminal name" }, { key: "currency", label: "Currency", value: org.data.value?.default_currency ?? "USD" }, { key: "opening_minor", label: "Opening cash", kind: "money", value: "0" }];
  if (mode.value === "close") return [{ key: "counted_minor", label: "Counted cash", kind: "money" }];
  if (mode.value === "review") return [{ key: "reason", label: "Review notes", kind: "textarea" }];
  if (mode.value === "movement") return [{ key: "amount_minor", label: "Cash added (+) or removed (−)", kind: "money", signed: true }, { key: "reason", label: "Reason", kind: "textarea" }];
  return [{ key: "customer_id", label: "Customer", kind: "select", options: customers.data.value ?? [] }, { key: "package_id", label: "Top-up package", kind: "select", required: false, options: [{ value: "", label: "Custom amount" }, ...(packages.data.value?.items ?? []).filter(p => p.active && p.currency === currency.value).map(p => ({ value: p.id, label: `${p.name}: ${formatMoney(p.paid_minor, p.currency)} + ${formatMoney(p.bonus_minor, p.currency)} bonus` }))] }, { key: "amount_minor", label: "Custom amount (leave blank for package)", kind: "money", required: false }];
});
const title = computed(() => ({ open: "Open cashier shift", topup: "Confirm cash top-up", close: "Close cashier shift", review: "Review cash variance", movement: "Record cash movement" })[mode.value ?? "open"]);
const save = useMutation({ mutationFn: async ({ values, key }: { values: Record<string, string | number | null>; key: string }) => {
  let path = "/admin/api/v1/shifts";
  let body: Record<string, unknown> = values;
  if (mode.value === "topup") {
    const selectedPackage = packages.data.value?.items.find(p => p.id === values.package_id);
    path = "/admin/api/v1/cashier/topups";
    body = { ...values, amount_minor: selectedPackage?.paid_minor ?? values.amount_minor, shift_id: shift.value?.id, currency: currency.value, idempotency_key: key };
  } else if (mode.value !== "open") {
    path += `/${shift.value?.id}/${mode.value === 'movement' ? 'movements' : mode.value}`;
    if (mode.value === "movement") body = { ...values, idempotency_key: key };
  }
  const result = await apiRequest<typeof receipt.value>(path, { method: "POST", body: JSON.stringify(body) });
  if (mode.value === "topup") receipt.value = result;
}, onSuccess: async () => { mode.value = null; await queryClient.invalidateQueries({ queryKey: ["resource"] }); await queryClient.invalidateQueries({ queryKey: ["overview"] }); } });
function action(value: typeof mode.value, row: ResourceRecord | null = null) { shift.value = row; save.reset(); mode.value = value; }
</script>
<template>
  <div class="grid gap-4">
    <p v-if="receipt" role="status" class="rounded border border-success bg-success-soft p-3 text-sm">Receipt {{ receipt.number }} · {{ formatMoney(receipt.paid_minor, receipt.currency) }} paid + {{ formatMoney(receipt.bonus_minor, receipt.currency) }} bonus credited.</p>
    <label v-if="permissions.has('shifts:review')" class="flex items-center gap-2 text-sm"><input v-model="reviewQueue" type="checkbox" /> View all cashier shifts</label>
    <ResourcePage title="Cashier shifts" description="Confirmed cash receipts and opening-to-closing reconciliation." :endpoint="endpoint" :columns="columns" row-actions>
      <template #actions><UiButton @click="action('open')">Open shift</UiButton></template>
      <template #row-action="{ row }"><div class="flex justify-end gap-2">
        <UiButton v-if="!row.closed_at && row.cashier_id === user?.id" variant="secondary" @click="action('topup', row)">Cash top-up</UiButton>
        <UiButton v-if="!row.closed_at && row.cashier_id === user?.id" variant="secondary" @click="action('close', row)">Close</UiButton>
        <UiButton v-if="!row.closed_at && permissions.has('shifts:review')" variant="secondary" @click="action('movement', row)">Cash movement</UiButton>
        <UiButton v-if="row.closed_at && permissions.has('shifts:review')" variant="secondary" @click="action('review', row)">Review</UiButton>
      </div></template>
    </ResourcePage>
    <ActionDrawer :open="Boolean(mode)" :title="title" :fields="fields" :currency="currency" :pending="save.isPending.value" :error="save.error.value?.message" @close="mode = null" @submit="(values, key) => save.mutate({ values, key })" />
    <ResourcePage title="Receipts" description="Paid and promotional funding recorded together." endpoint="/admin/api/v1/receipts" :columns="[{ key: 'number', label: 'Receipt' }, { key: 'paid_minor', label: 'Paid', kind: 'money' }, { key: 'bonus_minor', label: 'Bonus', kind: 'money' }, { key: 'tender', label: 'Tender' }, { key: 'created_at', label: 'Time' }]" />
  </div>
</template>
