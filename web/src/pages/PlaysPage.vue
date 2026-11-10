<script setup lang="ts">
import { computed, ref } from "vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import ResourcePage, { type ResourceColumn, type ResourceRecord } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import { useAuth } from "../auth/useAuth";

const { permissions } = useAuth();
const client = useQueryClient();
const filter = ref("");
const selected = ref<ResourceRecord | null>(null);
const endpoint = computed(() => `/admin/api/v1/plays${filter.value ? `?state=${filter.value}` : ''}`);
const columns: ResourceColumn[] = [{ key: "id", label: "Play" }, { key: "amount_minor", label: "Price", kind: "money" }, { key: "status", label: "Outcome", kind: "status" }, { key: "created_at", label: "Authorized" }, { key: "resolution_reason", label: "Recovery note" }];
const fields: ActionField[] = [{ key: "outcome", label: "Confirmed outcome", kind: "select", options: [{ value: "activated", label: "Machine activated" }, { value: "refunded", label: "No activation — refund" }] }, { key: "reason", label: "Evidence and reason", kind: "textarea" }];
const resolve = useMutation({ mutationFn: (values: Record<string, unknown>) => apiRequest(`/admin/api/v1/plays/${selected.value?.id}/resolve`, { method: "POST", body: JSON.stringify(values) }), onSuccess: async () => { selected.value = null; await client.invalidateQueries({ queryKey: ["resource"] }); } });
</script>
<template>
  <div class="grid gap-4">
    <label class="flex items-center gap-3 text-sm">Outcome <select v-model="filter" class="rounded border border-line bg-white p-2"><option value="">All plays</option><option value="unknown">Needs review</option><option value="authorized">Awaiting acknowledgement</option><option value="activated">Activated</option><option value="refunded">Refunded</option></select></label>
    <ResourcePage title="Machine plays" description="Payments, activation outcomes, and operator recovery." :endpoint="endpoint" :columns="columns" :row-actions="permissions.has('plays:resolve')">
      <template #row-action="{ row }"><UiButton v-if="row.status === 'unknown'" variant="secondary" @click="selected = row">Resolve</UiButton></template>
    </ResourcePage>
    <ActionDrawer :open="Boolean(selected)" title="Resolve machine play" :fields="fields" :pending="resolve.isPending.value" :error="resolve.error.value?.message" @close="selected = null" @submit="values => resolve.mutate(values)" />
  </div>
</template>
