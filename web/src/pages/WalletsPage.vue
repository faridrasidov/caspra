<script setup lang="ts">
import { RiWallet3Line } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref, watch } from "vue";

import { useAuth } from "../auth/useAuth";
import { toMinorUnits } from "../utils/format";
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
const { permissions } = useAuth();
const operationKey = ref(crypto.randomUUID());
watch([amount, wallet], () => { operationKey.value = crypto.randomUUID(); });
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
        idempotency_key: operationKey.value,
        amount_minor: toMinorUnits(amount.value, String(wallet.value?.currency)),
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
    :row-actions="permissions.has('wallets:adjust')"
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
        <input v-model="amount" type="text" inputmode="decimal" required />
      </FormField>
      <FormField label="Reason required"><input v-model="reason" required /></FormField>
      <p v-if="topup.error.value" class="text-[12px] text-danger" role="alert">{{ topup.error.value.message }}</p>
    </CommandForm>
  </AppDrawer>
</template>
