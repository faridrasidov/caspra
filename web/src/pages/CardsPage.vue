<script setup lang="ts">
import { RiBankCardLine } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import { apiRequest } from "../api/client";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import FormField from "../components/FormField.vue";
import ResourcePage, { type ResourceColumn } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";

const endpoint = "/admin/api/v1/cards";
const queryClient = useQueryClient();
const open = ref(false);
const uid = ref("");
const customerId = ref("");
const columns: ResourceColumn[] = [
  { key: "uid", label: "UID" },
  { key: "type", label: "Type" },
  { key: "customer_id", label: "Customer" },
  { key: "status", label: "Status", kind: "status" },
  { key: "created_at", label: "Registered" },
];
const create = useMutation({
  mutationFn: () =>
    apiRequest(endpoint, {
      method: "POST",
      body: JSON.stringify({ uid: uid.value, type: "rfid", customer_id: customerId.value || null }),
    }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
    open.value = false;
  },
});
</script>

<template>
  <ResourcePage
    title="Cards"
    description="RFID and NFC credentials assigned to customers."
    :endpoint="endpoint"
    :columns="columns"
  >
    <template #actions>
      <UiButton :icon="RiBankCardLine" @click="open = true">Register card</UiButton>
    </template>
  </ResourcePage>
  <AppDrawer title="Register card" :open="open" @close="open = false">
    <CommandForm
      submit-label="Register card"
      :submitting="create.isPending.value"
      @submit="create.mutate()"
      @cancel="open = false"
    >
      <FormField label="Card UID"><input v-model="uid" required /></FormField>
      <FormField label="Customer ID" hint="Optional; the card can be assigned later.">
        <input v-model="customerId" />
      </FormField>
      <p v-if="create.error.value" class="text-[12px] text-danger" role="alert">{{ create.error.value.message }}</p>
    </CommandForm>
  </AppDrawer>
</template>
