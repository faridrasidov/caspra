<script setup lang="ts">
import { RiAddLine, RiUploadLine } from "@remixicon/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, ref, watch } from "vue";

import {
  createCustomer,
  deleteCustomer,
  getCustomerBalances,
  importCustomers,
  updateCustomer,
  type CustomerCreate,
  type CustomerOut,
} from "../api/admin";
import { useAuth } from "../auth/useAuth";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import ConfirmAction from "../components/ConfirmAction.vue";
import FormField from "../components/FormField.vue";
import ResourcePage, {
  type ResourceColumn,
  type ResourceRecord,
} from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";
import { formatMoney } from "../utils/format";

const endpoint = "/admin/api/v1/customers";
const queryClient = useQueryClient();
const { permissions } = useAuth();
const canWrite = () => permissions.value.has("customers:write");

const createOpen = ref(false);
const importOpen = ref(false);
const selected = ref<CustomerOut | null>(null);
const deleting = ref(false);
const deleteReason = ref("");
const importText = ref("");
const importResult = ref("");
const fullName = ref("");
const email = ref("");
const phone = ref("");
const externalId = ref("");
const status = ref<CustomerOut["status"]>("active");

const columns: ResourceColumn[] = [
  { key: "full_name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "external_id", label: "External ID" },
  { key: "status", label: "Status", kind: "status" },
  { key: "created_at", label: "Created" },
];

const selectedId = computed(() => selected.value?.id);
const balances = useQuery({
  queryKey: computed(() => ["customer-balances", selectedId.value]),
  queryFn: () => getCustomerBalances(selectedId.value!),
  enabled: computed(() => Boolean(selectedId.value)),
});

watch(selected, (customer) => {
  if (!customer) return;
  fullName.value = customer.full_name ?? "";
  email.value = customer.email ?? "";
  phone.value = customer.phone ?? "";
  externalId.value = customer.external_id ?? "";
  status.value = customer.status;
});

function resetCreate() {
  createOpen.value = false;
  fullName.value = "";
  email.value = "";
  phone.value = "";
  externalId.value = "";
}

function closeDetail() {
  selected.value = null;
  deleting.value = false;
  deleteReason.value = "";
}

function parseImport(raw: string): CustomerCreate[] {
  const trimmed = raw.trim();
  if (!trimmed) throw new Error("Paste a JSON array or a CSV with a header row");
  if (trimmed.startsWith("[")) {
    const parsed = JSON.parse(trimmed) as CustomerCreate[];
    if (!Array.isArray(parsed) || parsed.length === 0) {
      throw new Error("JSON import must be a non-empty array");
    }
    return parsed;
  }
  const lines = trimmed.split(/\r?\n/).filter((line) => line.trim());
  const headers = (lines.shift() ?? "").split(",").map((header) => header.trim());
  if (!headers.length || !lines.length) throw new Error("CSV import needs a header and at least one row");
  return lines.map((line) => {
    const cols = line.split(",").map((col) => col.trim());
    const row: Record<string, string> = {};
    headers.forEach((header, index) => {
      row[header] = cols[index] ?? "";
    });
    return {
      full_name: row.full_name || null,
      email: row.email || null,
      phone: row.phone || null,
      external_id: row.external_id || null,
    };
  });
}

async function invalidate() {
  await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
  await queryClient.invalidateQueries({ queryKey: ["picker", endpoint] });
  await queryClient.invalidateQueries({ queryKey: ["customer-balances"] });
}

const create = useMutation({
  mutationFn: () =>
    createCustomer({
      full_name: fullName.value || null,
      email: email.value || null,
      phone: phone.value || null,
      external_id: externalId.value || null,
    }),
  onSuccess: async () => {
    await invalidate();
    resetCreate();
  },
});

const save = useMutation({
  mutationFn: () =>
    updateCustomer(selected.value!.id, {
      full_name: fullName.value || null,
      email: email.value || null,
      phone: phone.value || null,
      external_id: externalId.value || null,
      status: status.value,
    }),
  onSuccess: async () => {
    await invalidate();
    closeDetail();
  },
});

const remove = useMutation({
  mutationFn: () => deleteCustomer(selected.value!.id),
  onSuccess: async () => {
    await invalidate();
    closeDetail();
  },
});

const importing = useMutation({
  mutationFn: () => importCustomers(parseImport(importText.value)),
  onSuccess: async (result) => {
    await invalidate();
    importResult.value = `Created ${result.created}, skipped ${result.skipped}`;
  },
});

function openCreate() {
  selected.value = null;
  fullName.value = "";
  email.value = "";
  phone.value = "";
  externalId.value = "";
  createOpen.value = true;
}

function selectCustomer(row: ResourceRecord) {
  selected.value = row as CustomerOut;
}
</script>

<template>
  <ResourcePage
    title="Customers"
    description="Customer identities and stored-value relationships."
    :endpoint="endpoint"
    :columns="columns"
    @select="selectCustomer"
  >
    <template #actions>
      <UiButton
        v-if="canWrite()"
        :icon="RiUploadLine"
        variant="secondary"
        @click="importOpen = true"
      >
        Import
      </UiButton>
      <UiButton v-if="canWrite()" :icon="RiAddLine" @click="openCreate">Add customer</UiButton>
    </template>
  </ResourcePage>

  <AppDrawer title="Add customer" :open="createOpen" @close="resetCreate">
    <CommandForm
      submit-label="Create customer"
      :submitting="create.isPending.value"
      @submit="create.mutate()"
      @cancel="resetCreate"
    >
      <FormField label="Full name"><input v-model="fullName" required /></FormField>
      <FormField label="Email"><input v-model="email" type="email" /></FormField>
      <FormField label="Phone"><input v-model="phone" /></FormField>
      <FormField label="External ID"><input v-model="externalId" /></FormField>
      <p v-if="create.error.value" class="text-[12px] text-danger" role="alert">
        {{ create.error.value.message }}
      </p>
    </CommandForm>
  </AppDrawer>

  <AppDrawer title="Import customers" :open="importOpen" @close="importOpen = false; importText = ''; importResult = ''">
    <CommandForm
      submit-label="Import"
      :submitting="importing.isPending.value"
      @submit="importing.mutate()"
      @cancel="importOpen = false"
    >
      <FormField
        label="JSON or CSV"
        hint='JSON array or CSV with headers full_name,email,phone,external_id'
      >
        <textarea
          v-model="importText"
          placeholder='[{"full_name":"Ada Lovelace","email":"ada@example.com"}]'
          required
        />
      </FormField>
      <p v-if="importResult" class="text-[12px] text-success">{{ importResult }}</p>
      <p v-if="importing.error.value" class="text-[12px] text-danger" role="alert">
        {{ importing.error.value.message }}
      </p>
    </CommandForm>
  </AppDrawer>

  <AppDrawer :title="deleting ? 'Delete customer' : 'Edit customer'" :open="Boolean(selected)" @close="closeDetail">
    <ConfirmAction
      v-if="deleting"
      submit-label="Delete customer"
      :submitting="remove.isPending.value"
      message="This removes the customer record. Ledger entries stay immutable."
      :error="remove.error.value?.message"
      v-model:reason="deleteReason"
      @submit="remove.mutate()"
      @cancel="deleting = false"
    />
    <CommandForm
      v-else-if="selected"
      submit-label="Save customer"
      :submitting="save.isPending.value"
      @submit="save.mutate()"
      @cancel="closeDetail"
    >
      <FormField label="Full name"><input v-model="fullName" :disabled="!canWrite()" /></FormField>
      <FormField label="Email"><input v-model="email" type="email" :disabled="!canWrite()" /></FormField>
      <FormField label="Phone"><input v-model="phone" :disabled="!canWrite()" /></FormField>
      <FormField label="External ID"><input v-model="externalId" :disabled="!canWrite()" /></FormField>
      <FormField label="Status">
        <select v-model="status" :disabled="!canWrite()">
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="blocked">Blocked</option>
        </select>
      </FormField>
      <section class="grid gap-2">
        <h3 class="text-[11px] font-bold">Balances</h3>
        <p v-if="balances.isLoading.value" class="text-[11px] text-muted">Loading balances</p>
        <p v-else-if="balances.error.value" class="text-[11px] text-danger">{{ balances.error.value.message }}</p>
        <p v-else-if="!balances.data.value?.balances.length" class="text-[11px] text-muted">No wallets yet.</p>
        <ul v-else class="grid gap-1.5 text-[11px]">
          <li
            v-for="wallet in balances.data.value.balances"
            :key="wallet.wallet_id"
            class="flex justify-between gap-2"
          >
            <span>{{ wallet.type }} · {{ wallet.currency }}</span>
            <strong>{{ formatMoney(wallet.balance_minor, wallet.currency) }}</strong>
          </li>
        </ul>
      </section>
      <p v-if="save.error.value" class="text-[12px] text-danger" role="alert">
        {{ save.error.value.message }}
      </p>
      <UiButton
        v-if="canWrite()"
        type="button"
        variant="danger"
        @click="deleting = true"
      >
        Delete customer
      </UiButton>
    </CommandForm>
  </AppDrawer>
</template>
