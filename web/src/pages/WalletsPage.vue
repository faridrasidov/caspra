<script setup lang="ts">
import { RiArrowLeftRightLine, RiSubtractLine, RiWallet3Line } from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import {
  createWallet,
  deductWallet,
  topupWallet,
  transferWallet,
  type WalletType,
} from "../api/admin";
import { useAuth } from "../auth/useAuth";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import EntityPicker from "../components/EntityPicker.vue";
import FormField from "../components/FormField.vue";
import IconButton from "../components/IconButton.vue";
import MoneyField from "../components/MoneyField.vue";
import ResourcePage, {
  type ResourceColumn,
  type ResourceRecord,
} from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";
import { toMinor } from "../utils/format";

const endpoint = "/admin/api/v1/wallets";
const queryClient = useQueryClient();
const { permissions } = useAuth();
const canAdjust = () => permissions.value.has("wallets:adjust");

const wallet = ref<ResourceRecord | null>(null);
const mode = ref<"create" | "topup" | "deduct" | "transfer" | null>(null);
const amount = ref("");
const reason = ref("");
const customerId = ref("");
const currency = ref("USD");
const walletType = ref<WalletType>("credit");
const fromWalletId = ref("");
const toWalletId = ref("");

const columns: ResourceColumn[] = [
  { key: "id", label: "Wallet" },
  { key: "customer_id", label: "Customer" },
  { key: "type", label: "Type" },
  { key: "currency", label: "Currency" },
  { key: "balance_minor", label: "Balance", numeric: true, kind: "money" },
  { key: "status", label: "Status", kind: "status" },
];

function customerLabel(item: Record<string, unknown>) {
  return String(item.full_name || item.email || item.external_id || item.id);
}

function walletLabel(item: Record<string, unknown>) {
  return `${String(item.id).slice(0, 8)} · ${item.currency} · ${item.type}`;
}

function close() {
  wallet.value = null;
  mode.value = null;
  amount.value = "";
  reason.value = "";
  customerId.value = "";
  currency.value = "USD";
  walletType.value = "credit";
  fromWalletId.value = "";
  toWalletId.value = "";
}

function openMoney(row: ResourceRecord, next: "topup" | "deduct") {
  wallet.value = row;
  mode.value = next;
}

async function invalidate() {
  await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
  await queryClient.invalidateQueries({ queryKey: ["overview"] });
}

const create = useMutation({
  mutationFn: () =>
    createWallet({
      customer_id: customerId.value,
      currency: currency.value,
      type: walletType.value,
    }),
  onSuccess: async () => {
    await invalidate();
    close();
  },
});

const topup = useMutation({
  mutationFn: () =>
    topupWallet(String(wallet.value?.id), {
      amount_minor: toMinor(amount.value),
      currency: String(wallet.value?.currency ?? "USD"),
      description: reason.value,
    }),
  onSuccess: async () => {
    await invalidate();
    close();
  },
});

const deduct = useMutation({
  mutationFn: () =>
    deductWallet(String(wallet.value?.id), {
      amount_minor: toMinor(amount.value),
      currency: String(wallet.value?.currency ?? "USD"),
      description: reason.value,
    }),
  onSuccess: async () => {
    await invalidate();
    close();
  },
});

const transfer = useMutation({
  mutationFn: () =>
    transferWallet({
      from_wallet_id: fromWalletId.value,
      to_wallet_id: toWalletId.value,
      amount_minor: toMinor(amount.value),
      currency: currency.value,
      description: reason.value,
    }),
  onSuccess: async () => {
    await invalidate();
    close();
  },
});

const drawerTitle = {
  create: "Create wallet",
  topup: "Top up wallet",
  deduct: "Deduct wallet",
  transfer: "Transfer between wallets",
};
</script>

<template>
  <ResourcePage
    title="Wallets"
    description="Cached balances backed by immutable ledger entries."
    :endpoint="endpoint"
    :columns="columns"
    :row-actions="canAdjust()"
  >
    <template #actions>
      <UiButton
        v-if="canAdjust()"
        :icon="RiArrowLeftRightLine"
        variant="secondary"
        @click="mode = 'transfer'"
      >
        Transfer
      </UiButton>
      <UiButton v-if="canAdjust()" :icon="RiWallet3Line" @click="mode = 'create'">
        Create wallet
      </UiButton>
    </template>
    <template #row-action="{ row }">
      <span class="inline-flex gap-1.5">
        <IconButton label="Top up wallet" :icon="RiWallet3Line" @click="openMoney(row, 'topup')" />
        <IconButton label="Deduct wallet" :icon="RiSubtractLine" @click="openMoney(row, 'deduct')" />
      </span>
    </template>
  </ResourcePage>

  <AppDrawer
    :title="mode ? drawerTitle[mode] : 'Wallet'"
    :open="Boolean(mode)"
    @close="close"
  >
    <CommandForm
      v-if="mode === 'create'"
      submit-label="Create wallet"
      :submitting="create.isPending.value"
      @submit="create.mutate()"
      @cancel="close"
    >
      <EntityPicker
        v-model="customerId"
        label="Customer"
        endpoint="/admin/api/v1/customers"
        required
        :option-label="customerLabel"
      />
      <FormField label="Currency">
        <input v-model="currency" maxlength="3" required />
      </FormField>
      <FormField label="Type">
        <select v-model="walletType" required>
          <option value="credit">Credit</option>
          <option value="token">Token</option>
          <option value="loyalty">Loyalty</option>
        </select>
      </FormField>
      <p v-if="create.error.value" class="text-[12px] text-danger" role="alert">
        {{ create.error.value.message }}
      </p>
    </CommandForm>

    <CommandForm
      v-else-if="mode === 'topup' || mode === 'deduct'"
      :submit-label="mode === 'topup' ? 'Confirm top-up' : 'Confirm deduct'"
      :submitting="mode === 'topup' ? topup.isPending.value : deduct.isPending.value"
      @submit="mode === 'topup' ? topup.mutate() : deduct.mutate()"
      @cancel="close"
    >
      <MoneyField
        v-model="amount"
        :currency="String(wallet?.currency ?? 'USD')"
      />
      <FormField label="Reason required"><input v-model="reason" required /></FormField>
      <p
        v-if="(mode === 'topup' ? topup.error.value : deduct.error.value)"
        class="text-[12px] text-danger"
        role="alert"
      >
        {{ (mode === "topup" ? topup.error.value : deduct.error.value)?.message }}
      </p>
    </CommandForm>

    <CommandForm
      v-else-if="mode === 'transfer'"
      submit-label="Confirm transfer"
      :submitting="transfer.isPending.value"
      @submit="transfer.mutate()"
      @cancel="close"
    >
      <EntityPicker
        v-model="fromWalletId"
        label="From wallet"
        endpoint="/admin/api/v1/wallets"
        required
        :option-label="walletLabel"
      />
      <EntityPicker
        v-model="toWalletId"
        label="To wallet"
        endpoint="/admin/api/v1/wallets"
        required
        :option-label="walletLabel"
      />
      <FormField label="Currency">
        <input v-model="currency" maxlength="3" required />
      </FormField>
      <MoneyField v-model="amount" :currency="currency" />
      <FormField label="Reason required"><input v-model="reason" required /></FormField>
      <p v-if="transfer.error.value" class="text-[12px] text-danger" role="alert">
        {{ transfer.error.value.message }}
      </p>
    </CommandForm>
  </AppDrawer>
</template>
