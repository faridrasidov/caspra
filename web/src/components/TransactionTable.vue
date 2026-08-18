<script setup lang="ts">
import { RiMore2Line, RiRefund2Line } from "@remixicon/vue";

import type { TransactionOut } from "../api/client";
import { formatMoney, formatTime } from "../utils/format";
import DataState from "./DataState.vue";
import IconButton from "./IconButton.vue";
import StatusMark from "./StatusMark.vue";

defineProps<{
  transactions: TransactionOut[];
  refundable?: boolean;
}>();

const emit = defineEmits<{
  refund: [transaction: TransactionOut];
  select: [transaction: TransactionOut];
}>();

function canRefund(transaction: TransactionOut) {
  return ["debit", "capture"].includes(transaction.type) && transaction.status === "posted";
}
</script>

<template>
  <DataState v-if="!transactions.length" kind="empty" message="No transactions match this view." />
  <div v-else class="overflow-x-auto">
    <table class="w-full border-collapse text-left">
      <thead>
        <tr class="bg-subtle text-muted">
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-[9px] font-bold">Time</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-[9px] font-bold">Reference</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-[9px] font-bold">Wallet</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-[9px] font-bold">Type</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-right text-[9px] font-bold">Amount</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-[9px] font-bold">Status</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-[9px] font-bold">Channel</th>
          <th class="h-[42px] whitespace-nowrap border-b border-line px-2.5" aria-label="Actions" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="transaction in transactions"
          :key="transaction.id"
          class="cursor-pointer hover:bg-subtle/60"
          @click="emit('select', transaction)"
        >
          <td class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 text-[10px]">{{ formatTime(transaction.created_at) }}</td>
          <td class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 font-mono text-[10px]">{{ transaction.id.slice(0, 8).toUpperCase() }}</td>
          <td class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 font-mono text-[10px]">{{ transaction.wallet_id?.slice(0, 8).toUpperCase() ?? "-" }}</td>
          <td class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 text-[10px] capitalize">{{ transaction.type }}</td>
          <td
            class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 text-right text-[10px] tabular-nums"
            :class="['debit', 'refund'].includes(transaction.type) ? 'text-danger' : ''"
          >
            {{ formatMoney(transaction.amount_minor, transaction.currency) }}
          </td>
          <td class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 text-[10px]"><StatusMark :value="transaction.status" /></td>
          <td class="h-[42px] max-w-[260px] whitespace-nowrap border-b border-line px-2.5 text-[10px]">{{ transaction.device_id ? `Device ${transaction.device_id.slice(0, 5)}` : "Admin" }}</td>
          <td class="h-[42px] whitespace-nowrap border-b border-line px-2.5 text-right" @click.stop>
            <IconButton
              v-if="refundable && canRefund(transaction)"
              label="Refund transaction"
              :icon="RiRefund2Line"
              @click="emit('refund', transaction)"
            />
            <IconButton v-else label="Transaction actions" :icon="RiMore2Line" disabled />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
