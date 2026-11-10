<script setup lang="ts">
import { ref } from "vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import { useAuth } from "../auth/useAuth";
import ActionDrawer from "../components/ActionDrawer.vue";
import ResourcePage from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";

const { permissions } = useAuth();
const client = useQueryClient();
const open = ref(false);
const repairOpen = ref(false);
const repair = useMutation({ mutationFn: (values: Record<string, unknown>) => apiRequest("/admin/api/v1/ledger/repair-wallet-cache", { method: "POST", body: JSON.stringify(values) }), onSuccess: () => { repairOpen.value = false; result.value = "Wallet cache rebuilt from ledger entries. Run reconciliation before reopening writes."; } });
const result = ref("");
const reconcile = useMutation({ mutationFn: () => apiRequest<{ healthy: boolean }>("/admin/api/v1/ledger/reconciliation/run", { method: "POST" }), onSuccess: async data => { result.value = data.healthy ? "Ledger and wallet balances agree." : "Differences found. Financial writes are paused."; await client.invalidateQueries({ queryKey: ["overview"] }); } });
const resume = useMutation({ mutationFn: (values: Record<string, unknown>) => apiRequest("/admin/api/v1/ledger/resume", { method: "POST", body: JSON.stringify(values) }), onSuccess: () => { open.value = false; result.value = "Financial writes resumed after a healthy reconciliation."; } });
</script>
<template>
  <div class="grid gap-4">
    <div v-if="permissions.has('financial:controls')" class="flex flex-wrap gap-3"><UiButton :disabled="reconcile.isPending.value" @click="reconcile.mutate()">Run reconciliation</UiButton><UiButton variant="secondary" @click="repairOpen = true">Rebuild wallet cache</UiButton><UiButton variant="secondary" @click="open = true">Resume financial writes</UiButton></div>
    <p v-if="result" role="status" class="text-sm">{{ result }}</p><p v-if="reconcile.error.value" role="alert" class="text-sm text-danger">{{ reconcile.error.value.message }}</p>
    <ResourcePage title="Operational alerts" description="Persistent exceptions from device monitoring, machine plays, and financial checks." endpoint="/admin/api/v1/alerts" :columns="[{ key: 'kind', label: 'Type' }, { key: 'detail', label: 'Details' }, { key: 'created_at', label: 'First detected' }]" />
    <ActionDrawer :open="repairOpen" title="Rebuild wallet cache" :fields="[{ key: 'wallet_id', label: 'Wallet ID from reconciliation' }, { key: 'reason', label: 'Investigation and repair notes', kind: 'textarea' }]" :pending="repair.isPending.value" :error="repair.error.value?.message" @close="repairOpen = false" @submit="values => repair.mutate(values)" />
    <ActionDrawer :open="open" title="Resume financial writes" :fields="[{ key: 'reason', label: 'Repair and reopening notes', kind: 'textarea' }]" :pending="resume.isPending.value" :error="resume.error.value?.message" @close="open = false" @submit="values => resume.mutate(values)" />
  </div>
</template>
