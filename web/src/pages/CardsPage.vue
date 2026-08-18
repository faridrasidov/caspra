<script setup lang="ts">
import {
  RiBankCardLine,
  RiForbidLine,
  RiLockUnlockLine,
} from "@remixicon/vue";
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref } from "vue";

import {
  assignCard,
  blockCard,
  createCard,
  replaceCard,
  resetCard,
  unassignCard,
  unblockCard,
} from "../api/admin";
import { useAuth } from "../auth/useAuth";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import ConfirmAction from "../components/ConfirmAction.vue";
import EntityPicker from "../components/EntityPicker.vue";
import FormField from "../components/FormField.vue";
import IconButton from "../components/IconButton.vue";
import ResourcePage, {
  type ResourceColumn,
  type ResourceRecord,
} from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";

const endpoint = "/admin/api/v1/cards";
const queryClient = useQueryClient();
const { permissions } = useAuth();
const canWrite = () => permissions.value.has("cards:write");

const registerOpen = ref(false);
const uid = ref("");
const customerId = ref("");
const selected = ref<ResourceRecord | null>(null);
const action = ref<"assign" | "replace" | "reset" | null>(null);
const assignCustomerId = ref("");
const newUid = ref("");
const resetReason = ref("");

const columns: ResourceColumn[] = [
  { key: "uid", label: "UID" },
  { key: "type", label: "Type" },
  { key: "customer_id", label: "Customer" },
  { key: "status", label: "Status", kind: "status" },
  { key: "created_at", label: "Registered" },
];

function customerLabel(item: Record<string, unknown>) {
  return String(item.full_name || item.email || item.external_id || item.id);
}

async function invalidate() {
  await queryClient.invalidateQueries({ queryKey: ["resource", endpoint] });
}

function closeRegister() {
  registerOpen.value = false;
  uid.value = "";
  customerId.value = "";
}

function closeDetail() {
  selected.value = null;
  action.value = null;
  assignCustomerId.value = "";
  newUid.value = "";
  resetReason.value = "";
}

const create = useMutation({
  mutationFn: () =>
    createCard({
      uid: uid.value,
      type: "rfid",
      customer_id: customerId.value || null,
    }),
  onSuccess: async () => {
    await invalidate();
    closeRegister();
  },
});

const assign = useMutation({
  mutationFn: () => assignCard(String(selected.value?.id), assignCustomerId.value),
  onSuccess: async () => {
    await invalidate();
    closeDetail();
  },
});

const unassign = useMutation({
  mutationFn: () => unassignCard(String(selected.value?.id)),
  onSuccess: async () => {
    await invalidate();
    closeDetail();
  },
});

const block = useMutation({
  mutationFn: (card: ResourceRecord) => blockCard(card.id),
  onSuccess: invalidate,
});

const unblock = useMutation({
  mutationFn: (card: ResourceRecord) => unblockCard(card.id),
  onSuccess: invalidate,
});

const reset = useMutation({
  mutationFn: () => resetCard(String(selected.value?.id)),
  onSuccess: async () => {
    await invalidate();
    closeDetail();
  },
});

const replace = useMutation({
  mutationFn: () => replaceCard(String(selected.value?.id), newUid.value),
  onSuccess: async () => {
    await invalidate();
    closeDetail();
  },
});
</script>

<template>
  <ResourcePage
    title="Cards"
    description="RFID and NFC credentials assigned to customers."
    :endpoint="endpoint"
    :columns="columns"
    :row-actions="canWrite()"
    @select="selected = $event"
  >
    <template #actions>
      <UiButton
        v-if="canWrite()"
        :icon="RiBankCardLine"
        @click="selected = null; registerOpen = true"
      >
        Register card
      </UiButton>
    </template>
    <template #row-action="{ row }">
      <IconButton
        v-if="row.status === 'blocked'"
        label="Unblock card"
        :icon="RiLockUnlockLine"
        @click="unblock.mutate(row)"
      />
      <IconButton
        v-else
        label="Block card"
        :icon="RiForbidLine"
        @click="block.mutate(row)"
      />
    </template>
  </ResourcePage>

  <AppDrawer title="Register card" :open="registerOpen" @close="closeRegister">
    <CommandForm
      submit-label="Register card"
      :submitting="create.isPending.value"
      @submit="create.mutate()"
      @cancel="closeRegister"
    >
      <FormField label="Card UID"><input v-model="uid" required /></FormField>
      <EntityPicker
        v-model="customerId"
        label="Customer"
        hint="Optional; the card can be assigned later."
        endpoint="/admin/api/v1/customers"
        empty-label="Unassigned"
        allow-empty
        :option-label="customerLabel"
      />
      <p v-if="create.error.value" class="text-[12px] text-danger" role="alert">
        {{ create.error.value.message }}
      </p>
    </CommandForm>
  </AppDrawer>

  <AppDrawer
    :title="action === 'assign' ? 'Assign card' : action === 'replace' ? 'Replace card' : action === 'reset' ? 'Reset card' : 'Card'"
    :open="Boolean(selected)"
    @close="closeDetail"
  >
    <ConfirmAction
      v-if="action === 'reset'"
      submit-label="Reset card"
      :submitting="reset.isPending.value"
      message="Reset returns the card to active and unassigned."
      :error="reset.error.value?.message"
      v-model:reason="resetReason"
      @submit="reset.mutate()"
      @cancel="action = null"
    />
    <CommandForm
      v-else-if="action === 'assign'"
      submit-label="Assign card"
      :submitting="assign.isPending.value"
      @submit="assign.mutate()"
      @cancel="action = null"
    >
      <EntityPicker
        v-model="assignCustomerId"
        label="Customer"
        endpoint="/admin/api/v1/customers"
        required
        :option-label="customerLabel"
      />
      <p v-if="assign.error.value" class="text-[12px] text-danger" role="alert">
        {{ assign.error.value.message }}
      </p>
    </CommandForm>
    <CommandForm
      v-else-if="action === 'replace'"
      submit-label="Replace card"
      :submitting="replace.isPending.value"
      @submit="replace.mutate()"
      @cancel="action = null"
    >
      <FormField label="New card UID" hint="The customer link is preserved.">
        <input v-model="newUid" required />
      </FormField>
      <p v-if="replace.error.value" class="text-[12px] text-danger" role="alert">
        {{ replace.error.value.message }}
      </p>
    </CommandForm>
    <div v-else-if="selected" class="grid gap-4 p-5">
      <dl class="grid gap-2 text-[12px]">
        <div><dt class="text-[10px] text-muted">UID</dt><dd class="font-mono">{{ selected.uid }}</dd></div>
        <div><dt class="text-[10px] text-muted">Type</dt><dd>{{ selected.type }}</dd></div>
        <div><dt class="text-[10px] text-muted">Status</dt><dd>{{ selected.status }}</dd></div>
        <div><dt class="text-[10px] text-muted">Customer</dt><dd class="font-mono text-[11px]">{{ selected.customer_id ?? "Unassigned" }}</dd></div>
      </dl>
      <div v-if="canWrite()" class="grid gap-2">
        <UiButton variant="secondary" @click="action = 'assign'">Assign</UiButton>
        <UiButton
          v-if="selected.customer_id"
          variant="secondary"
          :disabled="unassign.isPending.value"
          @click="unassign.mutate()"
        >
          Unassign
        </UiButton>
        <UiButton variant="secondary" @click="action = 'replace'">Replace</UiButton>
        <UiButton variant="danger" @click="action = 'reset'">Reset</UiButton>
        <p v-if="unassign.error.value" class="text-[12px] text-danger" role="alert">
          {{ unassign.error.value.message }}
        </p>
      </div>
    </div>
  </AppDrawer>
</template>
