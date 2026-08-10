<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, ref } from "vue";

import { apiRequest, type Schemas } from "../api/client";
import { formatTime } from "../utils/format";
import DataState from "../components/DataState.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";

const queryClient = useQueryClient();
const page = 1;
const limit = 50;

const notifications = useQuery({
  queryKey: ["notifications", page, limit],
  queryFn: () =>
    apiRequest<Schemas["PaginatedNotificationOut"]>(
      `/admin/api/v1/notifications?page=${page}&limit=${limit}`,
    ),
});

const expanded = ref(new Set<string>());
const previewLength = 160;
const hasUnread = computed(
  () => (notifications.data.value?.items ?? []).some((item) => !item.read),
);

const markAllRead = useMutation({
  mutationFn: () => apiRequest<Schemas["NotificationReadAllResult"]>("/admin/api/v1/notifications/read-all", { method: "POST" }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications", page, limit] }),
});

function toggleMessage(id: string) {
  const next = new Set(expanded.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  expanded.value = next;
}

function visibleMessage(id: string, message: string) {
  if (expanded.value.has(id)) return message;
  if (message.length <= previewLength) return message;
  return `${message.slice(0, previewLength)}...`;
}
</script>

<template>
  <PageHeader title="Notifications" description="Tenant notifications and alerts feed." />
  <section class="overflow-hidden rounded-md border border-line bg-white">
    <header class="flex items-center justify-between gap-2 border-b border-line p-2.5">
      <p class="text-[12px] text-muted">
        {{ notifications.data.value?.total ?? 0 }} total notifications
      </p>
      <UiButton
        :disabled="!hasUnread || markAllRead.isPending.value"
        :variant="hasUnread ? 'primary' : 'secondary'"
        @click="markAllRead.mutate()"
      >
        {{ markAllRead.isPending.value ? "Marking..." : "Mark all as read" }}
      </UiButton>
    </header>
    <DataState v-if="notifications.isLoading.value" />
    <DataState
      v-else-if="notifications.error.value"
      kind="error"
      :message="notifications.error.value.message"
      retry
      @retry="notifications.refetch()"
    />
    <DataState
      v-else-if="!notifications.data.value?.items.length"
      kind="empty"
      message="No notifications to show."
    />
    <div v-else class="overflow-x-auto">
      <table class="w-full min-w-[980px] border-collapse text-left text-[11px]">
        <thead>
          <tr class="bg-subtle text-muted">
            <th class="border-b border-line px-3 py-2.5">Title</th>
            <th class="border-b border-line px-3 py-2.5">Level</th>
            <th class="border-b border-line px-3 py-2.5">Message</th>
            <th class="border-b border-line px-3 py-2.5">Status</th>
            <th class="border-b border-line px-3 py-2.5">Created</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="notification in notifications.data.value.items" :key="notification.id" class="align-top hover:bg-subtle/60">
            <td class="border-b border-line px-3 py-3">{{ notification.title }}</td>
            <td class="border-b border-line px-3 py-3">{{ notification.level }}</td>
            <td class="max-w-[450px] border-b border-line px-3 py-3">
              <p>{{ visibleMessage(notification.id, notification.message) }}</p>
              <button
                v-if="notification.message.length > previewLength"
                type="button"
                class="mt-1 text-[10px] text-primary hover:underline"
                @click="toggleMessage(notification.id)"
              >
                {{ expanded.has(notification.id) ? "Show less" : "Show more" }}
              </button>
            </td>
            <td class="border-b border-line px-3 py-3">
              <span
                class="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="notification.read ? 'bg-subtle text-muted' : 'bg-primary/12 text-primary'"
              >{{ notification.read ? "Read" : "Unread" }}</span>
            </td>
            <td class="border-b border-line px-3 py-3">{{ formatTime(notification.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
