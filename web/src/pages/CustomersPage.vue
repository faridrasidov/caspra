<script setup lang="ts">
import { RiAddLine } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import { apiRequest } from "../api/client";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import FormField from "../components/FormField.vue";
import ResourcePage, { type ResourceColumn } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";

const endpoint = "/admin/api/v1/customers";
const queryClient = useQueryClient();
const open = ref(false);
const fullName = ref("");
const email = ref("");
const externalId = ref("");
const columns: ResourceColumn[] = [
  { key: "full_name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "external_id", label: "External ID" },
  { key: "status", label: "Status", kind: "status" },
  { key: "created_at", label: "Created" },
];
const create = useMutation({
  mutationFn: () =>
    apiRequest(endpoint, {
      method: "POST",
      body: JSON.stringify({
        full_name: fullName.value || null,
        email: email.value || null,
        external_id: externalId.value || null,
      }),
    }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
    open.value = false;
  },
});
</script>

<template>
  <ResourcePage
    title="Customers"
    description="Customer identities and stored-value relationships."
    :endpoint="endpoint"
    :columns="columns"
  >
    <template #actions>
      <UiButton :icon="RiAddLine" @click="open = true">Add customer</UiButton>
    </template>
  </ResourcePage>
  <AppDrawer title="Add customer" :open="open" @close="open = false">
    <CommandForm
      submit-label="Create customer"
      :submitting="create.isPending.value"
      @submit="create.mutate()"
      @cancel="open = false"
    >
      <FormField label="Full name"><input v-model="fullName" required /></FormField>
      <FormField label="Email"><input v-model="email" type="email" /></FormField>
      <FormField label="External ID"><input v-model="externalId" /></FormField>
      <p v-if="create.error.value" class="text-[12px] text-danger" role="alert">{{ create.error.value.message }}</p>
    </CommandForm>
  </AppDrawer>
</template>
