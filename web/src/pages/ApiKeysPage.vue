<script setup lang="ts">
import { RiKey2Line } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import { apiRequest, type Schemas } from "../api/client";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import FormField from "../components/FormField.vue";
import ResourcePage, { type ResourceColumn } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";

const endpoint = "/admin/api/v1/api-keys";
const queryClient = useQueryClient();
const open = ref(false);
const name = ref("");
const createdKey = ref("");
const columns: ResourceColumn[] = [
  { key: "name", label: "Name" },
  { key: "prefix", label: "Prefix" },
  { key: "scopes", label: "Scopes" },
  { key: "last_used_at", label: "Last used" },
  { key: "revoked", label: "Status", kind: "revoked-status" },
];
const create = useMutation({
  mutationFn: () =>
    apiRequest<Schemas["ApiKeyCreateResult"]>(endpoint, {
      method: "POST",
      body: JSON.stringify({ name: name.value, scopes: [] }),
    }),
  onSuccess: async (result) => {
    await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
    createdKey.value = result.api_key;
  },
});

function close() {
  open.value = false;
  name.value = "";
  createdKey.value = "";
}

async function copyAndClose() {
  await navigator.clipboard.writeText(createdKey.value);
  close();
}
</script>

<template>
  <ResourcePage
    title="API keys"
    description="Tenant credentials for server-to-server integrations."
    :endpoint="endpoint"
    :columns="columns"
  >
    <template #actions>
      <UiButton :icon="RiKey2Line" @click="open = true">Create key</UiButton>
    </template>
  </ResourcePage>
  <AppDrawer title="Create API key" :open="open" @close="close">
    <div v-if="createdKey" class="grid gap-4 p-5">
      <p class="text-[12px] text-muted">This key is shown once.</p>
      <code class="overflow-x-auto rounded-md border border-line bg-subtle p-3 font-mono text-[11px]">{{ createdKey }}</code>
      <UiButton @click="copyAndClose">Copy and close</UiButton>
    </div>
    <CommandForm
      v-else
      submit-label="Create key"
      :submitting="create.isPending.value"
      @submit="create.mutate()"
      @cancel="close"
    >
      <FormField label="Key name"><input v-model="name" required /></FormField>
      <p v-if="create.error.value" class="text-[12px] text-danger" role="alert">{{ create.error.value.message }}</p>
    </CommandForm>
  </AppDrawer>
</template>
