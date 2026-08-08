<script setup lang="ts">
import { RiWallet3Line } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import { apiRequest } from "../api/client";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import FormField from "../components/FormField.vue";
import IconButton from "../components/IconButton.vue";
import ResourcePage, {
  type ResourceColumn,
  type ResourceRecord,
} from "../components/ResourcePage.vue";

const endpoint = "/admin/api/v1/wallets";
const queryClient = useQueryClient();
const wallet = ref<ResourceRecord | null>(null);
const amount = ref("");
const reason = ref("");
const columns: ResourceColumn[] = [
  { key: "id", label: "Wallet" },
  { key: "customer_id", label: "Customer" },
  { key: "type", label: "Type" },
  { key: "currency", label: "Currency" },
  { key: "balance_minor", label: "Balance", numeric: true, kind: "money" },
  { key: "status", label: "Status", kind: "status" },
];
const topup = useMutation({
  mutationFn: () =>
    apiRequest(`/admin/api/v1/wallets/${wallet.value?.id}/topup`, {
      method: "POST",
      body: JSON.stringify({
        idempotency_key: crypto.randomUUID(),
        amount_minor: Math.round(Number(amount.value) * 100),
        currency: wallet.value?.currency,
        description: reason.value,
      }),
    }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
    wallet.value = null;
    amount.value = "";
    reason.value = "";
  },
});
</script>

<template>
  <ResourcePage
    title="Wallets"
    description="Cached balances backed by immutable ledger entries."
    :endpoint="endpoint"
    :columns="columns"
    row-actions
  >
    <template #row-action="{ row }">
      <IconButton label="Top up wallet" :icon="RiWallet3Line" @click="wallet = row" />
    </template>
  </ResourcePage>
  <AppDrawer title="Top up wallet" :open="Boolean(wallet)" @close="wallet = null">
    <CommandForm
      submit-label="Confirm top-up"
      :submitting="topup.isPending.value"
      @submit="topup.mutate()"
      @cancel="wallet = null"
    >
      <FormField label="Amount">
        <input v-model="amount" type="number" min="0.01" step="0.01" required />
      </FormField>
      <FormField label="Reason required"><input v-model="reason" required /></FormField>
      <p v-if="topup.error.value" class="text-[12px] text-danger" role="alert">{{ topup.error.value.message }}</p>
    </CommandForm>
  </AppDrawer>
</template>
