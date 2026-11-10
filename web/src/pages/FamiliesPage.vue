<script setup lang="ts">
import { computed, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import { resourceOptions } from "../api/options";
import ResourcePage, { type ResourceColumn, type ResourceRecord } from "../components/ResourcePage.vue";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import UiButton from "../components/UiButton.vue";

const client = useQueryClient();
const open = ref(false);
const selected = ref<ResourceRecord | null>(null);
const customers = useQuery({ queryKey: ["customer-options"], queryFn: () => resourceOptions("/admin/api/v1/customers", "full_name") });
const org = useQuery({ queryKey: ["org"], queryFn: () => apiRequest<{ default_currency: string }>("/admin/api/v1/org") });
const labels = computed(() => Object.fromEntries((customers.data.value ?? []).map(c => [c.value, c.label])));
const columns = computed<ResourceColumn[]>(() => [{ key: "guardian_id", label: "Guardian", labels: labels.value }, { key: "child_id", label: "Child", labels: labels.value }, { key: "created_at", label: "Linked" }]);
const fields = computed<ActionField[]>(() => selected.value ? [{ key: "currency", label: "Currency", value: org.data.value?.default_currency ?? "USD" }, { key: "daily_minor", label: "Daily spending allowance", kind: "money" }] : [{ key: "guardian_id", label: "Guardian", kind: "select", options: customers.data.value ?? [] }, { key: "child_id", label: "Child", kind: "select", options: customers.data.value ?? [] }]);
const save = useMutation({ mutationFn: (values: Record<string, unknown>) => apiRequest(selected.value ? `/admin/api/v1/customers/${selected.value.child_id}/spending-limit` : "/admin/api/v1/families", { method: selected.value ? "PUT" : "POST", body: JSON.stringify(values) }), onSuccess: async () => { open.value = false; await client.invalidateQueries({ queryKey: ["resource"] }); } });
function edit(row: ResourceRecord | null) { selected.value = row; open.value = true; save.reset(); }
</script>
<template>
  <ResourcePage title="Families" description="Individual child wallets, guardian funding, and daily spending limits." endpoint="/admin/api/v1/families" :columns="columns" row-actions>
    <template #actions><UiButton @click="edit(null)">Link guardian and child</UiButton></template>
    <template #row-action="{ row }"><UiButton variant="secondary" @click="edit(row)">Set daily allowance</UiButton></template>
  </ResourcePage>
  <ActionDrawer :open="open" :title="selected ? 'Set child spending allowance' : 'Link family accounts'" :fields="fields" :pending="save.isPending.value" :error="save.error.value?.message" @close="open = false" @submit="values => save.mutate(values)" />
</template>
