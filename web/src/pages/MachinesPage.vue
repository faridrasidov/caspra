<script setup lang="ts">
import { computed, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import { resourceOptions } from "../api/options";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import ResourcePage, { type ResourceColumn, type ResourceRecord } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";
import { useAuth } from "../auth/useAuth";
import { amountInput } from "../utils/format";

const endpoint = "/admin/api/v1/machines";
const client = useQueryClient();
const { permissions } = useAuth();
const open = ref(false);
const selected = ref<ResourceRecord | null>(null);
const readers = useQuery({ queryKey: ["reader-options"], queryFn: () => resourceOptions("/admin/api/v1/devices"), enabled: computed(() => permissions.value.has("devices:read")) });
const org = useQuery({ queryKey: ["org"], queryFn: () => apiRequest<{ default_currency: string }>("/admin/api/v1/org") });
const fields = computed<ActionField[]>(() => selected.value ? [
  { key: "name", label: "Machine name", value: String(selected.value.name) },
  { key: "price_minor", label: "Price per play", kind: "money", value: amountInput(Number(selected.value.price_minor), String(selected.value.currency)) },
  { key: "state", label: "Operating state", kind: "select", value: String(selected.value.state), options: ["available", "maintenance", "offline", "archived"].map(value => ({ value, label: value })) },
] : [
  { key: "name", label: "Machine name" },
  { key: "device_id", label: "Reader", kind: "select", options: readers.data.value ?? [] },
  { key: "currency", label: "Currency", value: org.data.value?.default_currency ?? "USD" },
  { key: "price_minor", label: "Price per play", kind: "money" },
]);
const columns: ResourceColumn[] = [{ key: "name", label: "Machine" }, { key: "price_minor", label: "Play price", kind: "money" }, { key: "price_revision", label: "Price revision" }, { key: "state", label: "State", kind: "status" }];
const save = useMutation({ mutationFn: (values: Record<string, unknown>) => apiRequest(selected.value ? `${endpoint}/${selected.value.id}` : endpoint, { method: selected.value ? "PATCH" : "POST", body: JSON.stringify(values) }), onSuccess: async () => { open.value = false; await client.invalidateQueries({ queryKey: ["resource", endpoint] }); } });
function edit(row: ResourceRecord | null) { selected.value = row; open.value = true; }
</script>
<template>
  <ResourcePage title="Machines" description="Reader assignments, server-controlled prices, and availability." :endpoint="endpoint" :columns="columns" :row-actions="permissions.has('machines:manage')">
    <template #actions><UiButton v-if="permissions.has('machines:manage')" @click="edit(null)">Add machine</UiButton></template>
    <template #row-action="{ row }"><UiButton variant="secondary" @click="edit(row)">Edit</UiButton></template>
  </ResourcePage>
  <ActionDrawer :open="open" :title="selected ? 'Edit machine' : 'Add machine'" :fields="fields" :currency="String(selected?.currency ?? org.data.value?.default_currency ?? 'USD')" :pending="save.isPending.value" :error="save.error.value?.message" @close="open = false" @submit="values => save.mutate(values)" />
</template>
