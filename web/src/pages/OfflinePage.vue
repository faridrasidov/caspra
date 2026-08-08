<script setup lang="ts">
import { RiCheckLine, RiCloseLine, RiSettings3Line } from "@remixicon/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { ref, watch } from "vue";

import { apiRequest, type OfflineReviewItemOut, type Schemas } from "../api/client";
import AppDrawer from "../components/AppDrawer.vue";
import CommandForm from "../components/CommandForm.vue";
import DataState from "../components/DataState.vue";
import FormField from "../components/FormField.vue";
import IconButton from "../components/IconButton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusMark from "../components/StatusMark.vue";
import UiButton from "../components/UiButton.vue";
import { formatMoney, formatTime } from "../utils/format";

const queryClient = useQueryClient();
const selected = ref<OfflineReviewItemOut | null>(null);
const decision = ref<"accept" | "reject">("reject");
const reason = ref("");
const policyOpen = ref(false);
const review = useQuery({
  queryKey: ["offline-review"],
  queryFn: () => apiRequest<OfflineReviewItemOut[]>("/admin/api/v1/offline/review"),
});
const policy = useQuery({
  queryKey: ["offline-policy"],
  queryFn: () =>
    apiRequest<Schemas["OfflinePolicyOut"] | null>("/admin/api/v1/offline/policy"),
});
const decide = useMutation({
  mutationFn: () =>
    apiRequest(`/admin/api/v1/offline/review/${selected.value?.id}`, {
      method: "POST",
      body: JSON.stringify({ decision: decision.value, reason: reason.value }),
    }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["offline-review"] });
    selected.value = null;
    reason.value = "";
  },
});

const enabled = ref(false);
const riskAccepted = ref(false);
const maxTransaction = ref(0);
const maxCard = ref(0);
const maxDevice = ref(0);
const maxOutage = ref(0);
const queueAge = ref(3600);
const queueSize = ref(100);
watch(
  policy.data,
  (current) => {
    enabled.value = current?.enabled ?? false;
    riskAccepted.value = current?.uid_risk_accepted ?? false;
    maxTransaction.value = (current?.max_transaction_minor ?? 0) / 100;
    maxCard.value = (current?.max_card_total_minor ?? 0) / 100;
    maxDevice.value = (current?.max_device_total_minor ?? 0) / 100;
    maxOutage.value = (current?.max_outage_total_minor ?? 0) / 100;
    queueAge.value = current?.max_queue_age_seconds ?? 3600;
    queueSize.value = current?.max_queue_size ?? 100;
  },
  { immediate: true },
);
const updatePolicy = useMutation({
  mutationFn: () =>
    apiRequest("/admin/api/v1/offline/policy", {
      method: "PUT",
      body: JSON.stringify({
        enabled: enabled.value,
        uid_risk_accepted: riskAccepted.value,
        max_transaction_minor: Math.round(maxTransaction.value * 100),
        max_card_total_minor: Math.round(maxCard.value * 100),
        max_device_total_minor: Math.round(maxDevice.value * 100),
        max_outage_total_minor: Math.round(maxOutage.value * 100),
        max_queue_age_seconds: queueAge.value,
        max_queue_size: queueSize.value,
        sync_interval_seconds: 60,
      } satisfies Schemas["OfflinePolicyUpdate"]),
    }),
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: ["offline-policy"] });
    policyOpen.value = false;
  },
});

function select(item: OfflineReviewItemOut, value: "accept" | "reject") {
  decision.value = value;
  selected.value = item;
}
</script>

<template>
  <div>
    <PageHeader
      title="Offline reconciliation"
      description="Bounded-risk operations that need server or operator disposition."
    >
      <template #actions>
        <UiButton :icon="RiSettings3Line" variant="secondary" @click="policyOpen = true">
          Risk policy
        </UiButton>
      </template>
    </PageHeader>
    <section class="mb-3 flex min-h-14 items-center justify-between gap-5 rounded-md border border-line bg-white px-4 py-3 max-[760px]:items-start max-[760px]:flex-col max-[760px]:gap-2">
      <span class="flex items-center gap-2"><strong class="text-[11px]">Offline spending</strong><StatusMark :value="policy.data.value?.enabled ? 'enabled' : 'disabled'" /></span>
      <span class="text-[11px] text-muted">Per transaction <strong class="text-ink">{{ formatMoney(policy.data.value?.max_transaction_minor ?? 0) }}</strong></span>
      <span class="text-[11px] text-muted">Queue age <strong class="text-ink">{{ policy.data.value?.max_queue_age_seconds ?? 0 }} seconds</strong></span>
    </section>
    <section class="overflow-hidden rounded-md border border-line bg-white">
      <DataState v-if="review.isLoading.value" />
      <DataState
        v-else-if="review.error.value"
        kind="error"
        :message="review.error.value.message"
        retry
        @retry="review.refetch()"
      />
      <div v-else-if="review.data.value?.length" class="overflow-x-auto">
        <table class="w-full min-w-[860px] border-collapse text-left text-[11px]">
          <thead><tr class="bg-subtle text-muted"><th class="border-b border-line px-3 py-2.5">Occurred</th><th class="border-b border-line px-3 py-2.5">Device</th><th class="border-b border-line px-3 py-2.5">Sequence</th><th class="border-b border-line px-3 py-2.5">Card</th><th class="border-b border-line px-3 py-2.5 text-right">Amount</th><th class="border-b border-line px-3 py-2.5">Reason</th><th class="border-b border-line px-3 py-2.5" aria-label="Actions" /></tr></thead>
          <tbody>
            <tr v-for="item in review.data.value" :key="item.id" class="hover:bg-subtle/60">
              <td class="border-b border-line px-3 py-3">{{ formatTime(item.occurred_at) }}</td>
              <td class="border-b border-line px-3 py-3 font-mono text-[10px]">{{ item.device_id.slice(0, 8) }}</td>
              <td class="border-b border-line px-3 py-3">{{ item.sequence_number }}</td>
              <td class="border-b border-line px-3 py-3">{{ item.card_uid }}</td>
              <td class="border-b border-line px-3 py-3 text-right">{{ formatMoney(item.amount_minor) }}</td>
              <td class="border-b border-line px-3 py-3">{{ item.error }}</td>
              <td class="border-b border-line px-3 py-2 text-right"><span class="inline-flex gap-1.5"><IconButton label="Accept operation" :icon="RiCheckLine" @click="select(item, 'accept')" /><IconButton label="Reject operation" :icon="RiCloseLine" @click="select(item, 'reject')" /></span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <DataState v-else kind="empty" message="No offline operations are waiting for review." />
    </section>

    <AppDrawer :title="`${decision === 'accept' ? 'Accept' : 'Reject'} offline operation`" :open="Boolean(selected)" @close="selected = null">
      <CommandForm :submit-label="`Confirm ${decision}`" :submitting="decide.isPending.value" @submit="decide.mutate()" @cancel="selected = null">
        <FormField label="Reason required"><textarea v-model="reason" minlength="3" required /></FormField>
        <p v-if="decide.error.value" class="text-[12px] text-danger" role="alert">{{ decide.error.value.message }}</p>
      </CommandForm>
    </AppDrawer>

    <AppDrawer title="Offline risk policy" :open="policyOpen" @close="policyOpen = false">
      <CommandForm submit-label="Save policy" :submitting="updatePolicy.isPending.value" @submit="updatePolicy.mutate()" @cancel="policyOpen = false">
        <label class="flex items-center gap-2 text-[12px] font-semibold"><input v-model="enabled" type="checkbox" class="size-4 accent-primary" /><span>Enable offline spending</span></label>
        <label class="flex items-center gap-2 text-[12px] font-semibold"><input v-model="riskAccepted" type="checkbox" class="size-4 accent-primary" /><span>Accept UID-only card cloning risk</span></label>
        <div class="grid grid-cols-2 gap-3 max-[760px]:grid-cols-1">
          <FormField label="Per transaction"><input v-model.number="maxTransaction" type="number" min="0" step="0.01" required /></FormField>
          <FormField label="Per card"><input v-model.number="maxCard" type="number" min="0" step="0.01" required /></FormField>
          <FormField label="Per device"><input v-model.number="maxDevice" type="number" min="0" step="0.01" required /></FormField>
          <FormField label="Outage total"><input v-model.number="maxOutage" type="number" min="0" step="0.01" required /></FormField>
          <FormField label="Queue age (seconds)"><input v-model.number="queueAge" type="number" min="60" required /></FormField>
          <FormField label="Queue size"><input v-model.number="queueSize" type="number" min="1" max="500" required /></FormField>
        </div>
        <p v-if="updatePolicy.error.value" class="text-[12px] text-danger" role="alert">{{ updatePolicy.error.value.message }}</p>
      </CommandForm>
    </AppDrawer>
  </div>
</template>
