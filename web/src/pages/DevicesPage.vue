<script setup lang="ts">
import { RiRestartLine } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import { apiRequest } from "../api/client";
import { useAuth } from "../auth/useAuth";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import FormField from "../components/FormField.vue";
import IconButton from "../components/IconButton.vue";
import ResourcePage, {
  type ResourceColumn,
  type ResourceRecord,
} from "../components/ResourcePage.vue";
import ActionDrawer from "../components/ActionDrawer.vue";
import UiButton from "../components/UiButton.vue";

const endpoint = "/admin/api/v1/devices";
const queryClient = useQueryClient();
const { permissions } = useAuth();
const device = ref<ResourceRecord | null>(null);
const reason = ref("");
const provisionOpen = ref(false);
const credential = ref<{ id: string; hmac_secret: string } | null>(null);
const provision = useMutation({
  mutationFn: (values: Record<string, unknown>) => apiRequest<{ id: string; hmac_secret: string }>(endpoint, { method: "POST", body: JSON.stringify({ ...values, type: "reader", legacy_payments_enabled: false }) }),
  onSuccess: async data => { credential.value = data; provisionOpen.value = false; await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] }); },
});
const columns: ResourceColumn[] = [
  { key: "name", label: "Device" },
  { key: "serial", label: "Serial" },
  { key: "type", label: "Type" },
  { key: "location_id", label: "Location" },
  { key: "status", label: "Status", kind: "status" },
  { key: "connectivity", label: "Connection", kind: "status" },
  { key: "last_seen", label: "Last heartbeat" },
];
const reset = useMutation({
  mutationFn: () =>
    apiRequest(`/admin/api/v1/devices/${device.value?.id}/reset`, {
      method: "POST",
      body: JSON.stringify({ reason: reason.value }),
    }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
    device.value = null;
    reason.value = "";
  },
});
</script>

<template>
  <ResourcePage
    title="Devices"
    description="Reader, kiosk, and gateway fleet status."
    :endpoint="endpoint"
    :columns="columns"
    :row-actions="permissions.has('devices:manage')"
  >
    <template #actions><UiButton v-if="permissions.has('devices:credentials')" @click="provisionOpen = true">Register reader</UiButton></template>
    <template #row-action="{ row }">
      <IconButton label="Queue device reset" :icon="RiRestartLine" @click="device = row" />
    </template>
  </ResourcePage>
  <section v-if="credential" class="mt-4 rounded border border-warning bg-white p-4 text-sm" role="status"><h2 class="font-bold">Reader credentials · shown once</h2><p class="mt-2">Copy these into the reader's secure configuration before dismissing.</p><dl class="mt-3 grid gap-2"><dt>Device ID</dt><dd class="break-all font-mono">{{ credential.id }}</dd><dt>HMAC secret</dt><dd class="break-all font-mono">{{ credential.hmac_secret }}</dd></dl><UiButton class="mt-4" variant="secondary" @click="credential = null">Dismiss credentials</UiButton></section>
  <ActionDrawer :open="provisionOpen" title="Register reader" :fields="[{ key: 'name', label: 'Reader name' }, { key: 'serial', label: 'Serial number', required: false }]" :pending="provision.isPending.value" :error="provision.error.value?.message" @close="provisionOpen = false" @submit="values => provision.mutate(values)" />
  <AppDrawer title="Queue device reset" :open="Boolean(device)" @close="device = null">
    <CommandForm
      submit-label="Queue reset"
      :submitting="reset.isPending.value"
      @submit="reset.mutate()"
      @cancel="device = null"
    >
      <FormField label="Reason required">
        <textarea v-model="reason" minlength="3" maxlength="500" required />
      </FormField>
      <p v-if="reset.error.value" class="text-[12px] text-danger" role="alert">{{ reset.error.value.message }}</p>
    </CommandForm>
  </AppDrawer>
</template>
