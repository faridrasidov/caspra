<script setup lang="ts">
import { RiRefreshLine } from "@remixicon/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, ref } from "vue";

import { apiRequest, type Schemas } from "../api/client";
import DataState from "../components/DataState.vue";
import IconButton from "../components/IconButton.vue";
import PageHeader from "../components/PageHeader.vue";
import StatusMark from "../components/StatusMark.vue";
import { formatTime } from "../utils/format";

const queryClient = useQueryClient();
const view = ref<"subscriptions" | "deliveries">("deliveries");
const subscriptions = useQuery({
  queryKey: ["webhooks"],
  queryFn: () =>
    apiRequest<Schemas["PaginatedWebhookOut"]>(
      "/admin/api/v1/webhooks?page=1&limit=100",
    ),
});
const deliveries = useQuery({
  queryKey: ["webhook-deliveries"],
  queryFn: () =>
    apiRequest<Schemas["PaginatedWebhookDeliveryOut"]>(
      "/admin/api/v1/webhooks/deliveries?page=1&limit=100",
    ),
});
const replay = useMutation({
  mutationFn: (id: string) =>
    apiRequest(`/admin/api/v1/webhooks/deliveries/${id}/replay`, { method: "POST" }),
  onSuccess: () =>
    queryClient.invalidateQueries({ queryKey: ["webhook-deliveries"] }),
});
const activeLoading = computed(() =>
  view.value === "deliveries" ? deliveries.isLoading.value : subscriptions.isLoading.value,
);
const activeError = computed(() =>
  view.value === "deliveries" ? deliveries.error.value : subscriptions.error.value,
);
</script>

<template>
  <div>
    <PageHeader
      title="Webhooks"
      description="Signed event subscriptions, retries, and dead-letter recovery."
    />
    <div class="mb-3 inline-flex overflow-hidden rounded-md border border-line bg-white">
      <button
        class="h-9 border-r border-line px-3.5 text-[11px] font-semibold"
        :class="view === 'deliveries' ? 'bg-primary text-white' : 'text-muted'"
        @click="view = 'deliveries'"
      >Deliveries</button>
      <button
        class="h-9 px-3.5 text-[11px] font-semibold"
        :class="view === 'subscriptions' ? 'bg-primary text-white' : 'text-muted'"
        @click="view = 'subscriptions'"
      >Subscriptions</button>
    </div>
    <section class="overflow-hidden rounded-md border border-line bg-white">
      <DataState v-if="activeLoading" />
      <DataState
        v-else-if="activeError"
        kind="error"
        :message="activeError.message"
        retry
        @retry="view === 'deliveries' ? deliveries.refetch() : subscriptions.refetch()"
      />
      <div v-else-if="view === 'deliveries' && deliveries.data.value?.items.length" class="overflow-x-auto">
        <table class="w-full min-w-[900px] border-collapse text-left text-[11px]">
          <thead><tr class="bg-subtle text-muted"><th class="border-b border-line px-3 py-2.5">Created</th><th class="border-b border-line px-3 py-2.5">Event</th><th class="border-b border-line px-3 py-2.5">Status</th><th class="border-b border-line px-3 py-2.5">Attempts</th><th class="border-b border-line px-3 py-2.5">Response</th><th class="border-b border-line px-3 py-2.5">Next retry</th><th class="border-b border-line px-3 py-2.5" aria-label="Actions" /></tr></thead>
          <tbody>
            <tr v-for="delivery in deliveries.data.value.items" :key="delivery.id" class="hover:bg-subtle/60">
              <td class="border-b border-line px-3 py-3">{{ formatTime(delivery.created_at) }}</td>
              <td class="border-b border-line px-3 py-3">{{ delivery.event_type }}</td>
              <td class="border-b border-line px-3 py-3"><StatusMark :value="delivery.status" /></td>
              <td class="border-b border-line px-3 py-3">{{ delivery.attempts }}</td>
              <td class="border-b border-line px-3 py-3">{{ delivery.response_code ?? delivery.error ?? "-" }}</td>
              <td class="border-b border-line px-3 py-3">{{ formatTime(delivery.next_retry_at) }}</td>
              <td class="border-b border-line px-3 py-2 text-right"><IconButton label="Replay delivery" :icon="RiRefreshLine" :disabled="replay.isPending.value" @click="replay.mutate(delivery.id)" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <DataState v-else-if="view === 'deliveries'" kind="empty" message="No webhook deliveries have been queued." />
      <div v-else-if="subscriptions.data.value?.items.length" class="overflow-x-auto">
        <table class="w-full min-w-[620px] border-collapse text-left text-[11px]">
          <thead><tr class="bg-subtle text-muted"><th class="border-b border-line px-3 py-2.5">Destination</th><th class="border-b border-line px-3 py-2.5">Events</th><th class="border-b border-line px-3 py-2.5">Status</th></tr></thead>
          <tbody><tr v-for="webhook in subscriptions.data.value.items" :key="webhook.id" class="hover:bg-subtle/60"><td class="border-b border-line px-3 py-3">{{ webhook.url }}</td><td class="border-b border-line px-3 py-3">{{ (webhook.events ?? []).join(', ') }}</td><td class="border-b border-line px-3 py-3"><StatusMark :value="webhook.active ? 'active' : 'inactive'" /></td></tr></tbody>
        </table>
      </div>
      <DataState v-else kind="empty" message="No webhook subscriptions are configured." />
    </section>
  </div>
</template>
