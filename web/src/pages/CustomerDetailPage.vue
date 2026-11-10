<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { useMutation, useQuery } from "@tanstack/vue-query";
import { apiRequest, type Schemas } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { formatMoney, formatTime } from "../utils/format";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import DataState from "../components/DataState.vue";
import PageHeader from "../components/PageHeader.vue";
import TransactionTable from "../components/TransactionTable.vue";
import UiButton from "../components/UiButton.vue";

const route = useRoute();
const { permissions } = useAuth();
const mode = ref<"block" | "replace" | "invite" | "status" | null>(null);
const cardId = ref("");
const invitation = ref("");
const workspace = useQuery({ queryKey: computed(() => ["customer-workspace", route.params.id]), queryFn: () => apiRequest<Schemas["CustomerWorkspace"]>(`/admin/api/v1/customers/${route.params.id}/workspace`), refetchInterval: 15000 });
const fields = computed<ActionField[]>(() => mode.value === "replace" ? [{ key: "new_uid", label: "Replacement card UID" }] : mode.value === "invite" ? [{ key: "email", label: "Portal email", kind: "email", value: workspace.data.value?.customer.email ?? "" }] : mode.value === "status" ? [{ key: "status", label: "Customer access", kind: "select", options: [{ value: "active", label: "Active" }, { value: "blocked", label: "Blocked" }, { value: "inactive", label: "Inactive" }] }] : [{ key: "confirmation", label: "Type BLOCK to confirm" }]);
const save = useMutation({ mutationFn: async (values: Record<string, unknown>) => {
  if (mode.value === "block" && values.confirmation !== "BLOCK") throw new Error("Type BLOCK to confirm");
  const path = mode.value === "invite" ? `/admin/api/v1/customers/${route.params.id}/portal-invitation` : mode.value === "status" ? `/admin/api/v1/customers/${route.params.id}` : `/admin/api/v1/cards/${cardId.value}/${mode.value}`;
  const result = await apiRequest<{ invitation_token?: string }>(path, { method: mode.value === "status" ? "PATCH" : "POST", ...(mode.value === "block" ? {} : { body: JSON.stringify(values) }) });
  if (result.invitation_token) invitation.value = `${window.location.origin}/portal#invite=${encodeURIComponent(result.invitation_token)}`;
}, onSuccess: async () => { mode.value = null; await workspace.refetch(); } });
function cardAction(action: "block" | "replace", id: string) { cardId.value = id; mode.value = action; save.reset(); }
</script>
<template>
  <DataState v-if="workspace.isLoading.value" />
  <DataState v-else-if="workspace.error.value" kind="error" :message="workspace.error.value.message" />
  <div v-else-if="workspace.data.value" class="grid gap-5">
    <PageHeader :title="workspace.data.value.customer.full_name ?? 'Customer account'" description="Cards, reservations, funding, and the latest 100 account events.">
      <template #actions><div class="flex gap-2"><UiButton v-if="permissions.has('customers:write')" variant="secondary" @click="mode = 'status'">Customer access</UiButton><UiButton v-if="permissions.has('portal:manage')" @click="mode = 'invite'">Issue portal link</UiButton></div></template>
    </PageHeader>
    <div v-if="invitation" class="rounded border border-warning bg-warning-soft p-4 text-sm"><p>One-time portal link · expires in 24 hours. Share directly with the verified customer.</p><a :href="invitation" class="mt-2 block break-all underline">{{ invitation }}</a><button class="mt-2 underline" @click="invitation = ''">Dismiss link</button></div>
    <section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Customer balances"><article v-for="wallet in workspace.data.value.wallets" :key="wallet.id" class="rounded border border-line bg-white p-4"><p class="text-xs text-muted">{{ wallet.type }} · {{ wallet.currency }} · {{ wallet.status }}</p><strong class="mt-2 block text-xl">{{ formatMoney(wallet.balance_minor, wallet.currency) }}</strong><p class="mt-2 text-xs text-muted">Reserved {{ formatMoney(workspace.data.value.reserved_minor[wallet.id] ?? 0, wallet.currency) }} · available {{ formatMoney(wallet.balance_minor - (workspace.data.value.reserved_minor[wallet.id] ?? 0), wallet.currency) }}</p></article></section>
    <section class="rounded border border-line bg-white p-4"><h2 class="mb-3 font-semibold">Cards</h2><div v-for="card in workspace.data.value.cards" :key="card.id" class="flex flex-wrap items-center justify-between gap-3 border-t border-line py-3 text-sm"><span>{{ card.uid }} · {{ card.status }}</span><div v-if="permissions.has('cards:write')" class="flex gap-2"><UiButton v-if="card.status === 'active'" variant="secondary" @click="cardAction('block', card.id)">Block</UiButton><UiButton variant="secondary" @click="cardAction('replace', card.id)">Replace</UiButton></div></div></section>
    <section class="overflow-hidden rounded border border-line bg-white"><h2 class="p-4 font-semibold">Recent transactions</h2><TransactionTable :transactions="workspace.data.value.transactions" /></section>
    <section class="rounded border border-line bg-white p-4"><h2 class="mb-3 font-semibold">Receipts</h2><p v-if="!workspace.data.value.receipts.length" class="text-sm text-muted">No receipts yet.</p><div v-for="receipt in workspace.data.value.receipts" :key="receipt.id" class="border-t border-line py-3 text-sm">{{ receipt.number }} · {{ formatMoney(receipt.paid_minor, receipt.currency) }} paid + {{ formatMoney(receipt.bonus_minor, receipt.currency) }} bonus · {{ formatTime(receipt.created_at) }}</div></section>
    <ActionDrawer :open="Boolean(mode)" :title="mode === 'invite' ? 'Issue customer portal link' : mode === 'status' ? 'Update customer access' : mode === 'replace' ? 'Replace lost card' : 'Block card'" :fields="fields" :pending="save.isPending.value" :error="save.error.value?.message" @close="mode = null" @submit="values => save.mutate(values)" />
  </div>
</template>
