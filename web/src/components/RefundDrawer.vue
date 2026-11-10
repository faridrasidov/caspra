<script setup lang="ts">
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { ref, watch } from "vue";

import { apiRequest, type TransactionOut } from "../api/client";
import { amountInput, toMinorUnits, formatMoney, formatTime } from "../utils/format";
import AppDrawer from "./AppDrawer.vue";
import CommandForm from "./CommandForm.vue";
import FormField from "./FormField.vue";

const props = defineProps<{ transaction: TransactionOut | null }>();
const emit = defineEmits<{ close: [] }>();
const queryClient = useQueryClient();
const amount = ref("");
const reason = ref("");
const operationKey = ref(crypto.randomUUID());
watch([amount, reason], () => { operationKey.value = crypto.randomUUID(); });

watch(
  () => props.transaction,
  (transaction) => {
    amount.value = transaction ? amountInput(transaction.amount_minor, transaction.currency) : "";
    reason.value = "";
  },
  { immediate: true },
);

const refund = useMutation({
  mutationFn: async () => {
    if (!props.transaction) return;
    await apiRequest(`/admin/api/v1/transactions/${props.transaction.id}/refund`, {
      method: "POST",
      body: JSON.stringify({
        idempotency_key: operationKey.value,
        amount_minor: toMinorUnits(amount.value, props.transaction.currency),
        reason: reason.value,
      }),
    });
  },
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["transactions"] });
    await queryClient.invalidateQueries({ queryKey: ["overview"] });
    emit("close");
  },
});
</script>

<template>
  <AppDrawer title="Refund transaction" :open="Boolean(transaction)" @close="$emit('close')">
    <CommandForm
      v-if="transaction"
      submit-label="Confirm refund"
      :submitting="refund.isPending.value"
      @submit="refund.mutate()"
      @cancel="$emit('close')"
    >
      <dl class="mb-2.5 grid gap-[11px]">
        <div class="grid grid-cols-[120px_1fr] gap-2.5">
          <dt class="text-[10px] text-muted">Transaction</dt>
          <dd class="text-right font-mono text-[11px]">{{ transaction.id.slice(0, 12).toUpperCase() }}</dd>
        </div>
        <div class="grid grid-cols-[120px_1fr] gap-2.5">
          <dt class="text-[10px] text-muted">Time</dt>
          <dd class="text-right text-[11px]">{{ formatTime(transaction.created_at) }}</dd>
        </div>
        <div class="grid grid-cols-[120px_1fr] gap-2.5">
          <dt class="text-[10px] text-muted">Original amount</dt>
          <dd class="text-right text-[11px]">{{ formatMoney(transaction.amount_minor, transaction.currency) }}</dd>
        </div>
      </dl>
      <FormField
        label="Refund amount"
        :hint="`Maximum ${formatMoney(transaction.amount_minor, transaction.currency)}`"
      >
        <input
          v-model="amount"
          type="text"
          inputmode="decimal"
          required
        />
      </FormField>
      <FormField label="Reason required">
        <select v-model="reason" required>
          <option value="">Select reason</option>
          <option value="Customer request">Customer request</option>
          <option value="Duplicate charge">Duplicate charge</option>
          <option value="Operator correction">Operator correction</option>
          <option value="Service issue">Service issue</option>
        </select>
      </FormField>
      <p v-if="refund.error.value" class="text-[12px] text-danger" role="alert">
        {{ refund.error.value.message }}
      </p>
    </CommandForm>
  </AppDrawer>
</template>
