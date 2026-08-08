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

const endpoint = "/admin/api/v1/devices";
const queryClient = useQueryClient();
const { permissions } = useAuth();
const device = ref<ResourceRecord | null>(null);
const reason = ref("");
const columns: ResourceColumn[] = [
  { key: "name", label: "Device" },
  { key: "serial", label: "Serial" },
  { key: "type", label: "Type" },
  { key: "location_id", label: "Location" },
  { key: "status", label: "Status", kind: "status" },
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
    <template #row-action="{ row }">
      <IconButton label="Queue device reset" :icon="RiRestartLine" @click="device = row" />
    </template>
  </ResourcePage>
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
