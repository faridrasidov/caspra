<script setup lang="ts">
import { computed, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import ResourcePage, { type ResourceRecord } from "../components/ResourcePage.vue";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import UiButton from "../components/UiButton.vue";

const queryClient = useQueryClient();
const open = ref(false);
const selected = ref<ResourceRecord | null>(null);
const roles = useQuery({ queryKey: ["staff-roles"], queryFn: () => apiRequest<{ id: string; name: string; permissions: string[] }[]>("/admin/api/v1/staff/roles") });
const fields = computed<ActionField[]>(() => selected.value ? [
  { key: "role_id", label: "Staff role", kind: "select", value: String(selected.value.role_id ?? ''), options: roles.data.value?.map(r => ({ value: r.id, label: r.name })) ?? [] },
  { key: "status", label: "Access", kind: "select", value: String(selected.value.status), options: [{ value: "active", label: "Active" }, { value: "inactive", label: "Deactivated" }, { value: "suspended", label: "Suspended" }] },
] : [{ key: "full_name", label: "Full name" }, { key: "email", label: "Email", kind: "email" }, { key: "password", label: "Initial password", kind: "password" }, { key: "role_id", label: "Staff role", kind: "select", options: roles.data.value?.map(r => ({ value: r.id, label: r.name })) ?? [] }]);
const save = useMutation({ mutationFn: (values: Record<string, unknown>) => apiRequest(`/admin/api/v1/org/users${selected.value ? `/${selected.value.id}` : ''}`, { method: selected.value ? "PATCH" : "POST", body: JSON.stringify(values) }), onSuccess: async () => { open.value = false; await queryClient.invalidateQueries({ queryKey: ["resource", "/admin/api/v1/org/users"] }); } });
function edit(row: ResourceRecord | null) { selected.value = row; save.reset(); open.value = true; }
</script>
<template>
  <ResourcePage title="Staff access" description="Cashier, technician, manager, and owner permissions. Deactivation preserves financial history." endpoint="/admin/api/v1/org/users" :columns="[{ key: 'full_name', label: 'Name' }, { key: 'email', label: 'Email' }, { key: 'status', label: 'Access', kind: 'status' }]" row-actions>
    <template #actions><UiButton @click="edit(null)">Add staff member</UiButton></template>
    <template #row-action="{ row }"><UiButton variant="secondary" @click="edit(row)">Manage access</UiButton></template>
  </ResourcePage>
  <ActionDrawer :open="open" :title="selected ? 'Manage staff access' : 'Add staff member'" :fields="fields" :pending="save.isPending.value" :error="save.error.value?.message" @close="open = false" @submit="values => save.mutate(values)" />
</template>
