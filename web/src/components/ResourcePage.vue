<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import { computed, ref } from "vue";

import { apiRequest } from "../api/client";
import { formatMoney, renderValue } from "../utils/format";
import DataState from "./DataState.vue";
import PageHeader from "./PageHeader.vue";
import SearchField from "./SearchField.vue";
import StatusMark from "./StatusMark.vue";

export type ResourceRecord = Record<string, unknown> & { id: string };
export type ResourceColumn = {
  key: string;
  label: string;
  numeric?: boolean;
  kind?: "status" | "money" | "revoked-status";
  currencyKey?: string;
};

type PaginatedResult = {
  items: ResourceRecord[];
  total: number;
  page: number;
  limit: number;
};

const props = defineProps<{
  title: string;
  description: string;
  endpoint: string;
  columns: ResourceColumn[];
  rowActions?: boolean;
}>();

const search = ref("");
const resource = useQuery({
  queryKey: ["resource", props.endpoint],
  queryFn: () => apiRequest<PaginatedResult>(`${props.endpoint}?page=1&limit=100`),
});
const rows = computed(() => {
  const normalized = search.value.trim().toLowerCase();
  if (!normalized) return resource.data.value?.items ?? [];
  return (resource.data.value?.items ?? []).filter((row) =>
    JSON.stringify(row).toLowerCase().includes(normalized),
  );
});

function cellValue(row: ResourceRecord, column: ResourceColumn) {
  if (column.kind === "money") {
    return formatMoney(
      Number(row[column.key]),
      String(row[column.currencyKey ?? "currency"] ?? "USD"),
    );
  }
  return renderValue(row[column.key]);
}
</script>

<template>
  <div>
    <PageHeader :title="title" :description="description">
      <template v-if="$slots.actions" #actions><slot name="actions" /></template>
    </PageHeader>
    <section class="overflow-hidden rounded-md border border-line bg-white">
      <div class="flex min-h-14 items-center justify-between gap-3 border-b border-line p-2.5 max-[760px]:flex-col max-[760px]:items-stretch">
        <SearchField v-model="search" :placeholder="`Search ${title.toLowerCase()}`" />
        <span class="text-[10px] text-muted">{{ resource.data.value?.total ?? 0 }} records</span>
      </div>
      <DataState v-if="resource.isLoading.value" />
      <DataState
        v-else-if="resource.error.value"
        kind="error"
        :message="resource.error.value.message"
        retry
        @retry="resource.refetch()"
      />
      <div v-else-if="rows.length" class="overflow-x-auto">
        <table class="w-full min-w-[760px] border-collapse text-left text-[11px]">
          <thead>
            <tr class="bg-subtle text-muted">
              <th
                v-for="column in columns"
                :key="column.key"
                class="border-b border-line px-3 py-2.5 font-semibold"
                :class="column.numeric ? 'text-right' : ''"
              >
                {{ column.label }}
              </th>
              <th v-if="rowActions" class="border-b border-line px-3 py-2.5" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id" class="hover:bg-subtle/60">
              <td
                v-for="column in columns"
                :key="column.key"
                class="border-b border-line px-3 py-3 capitalize"
                :class="[
                  column.numeric ? 'text-right tabular-nums' : '',
                  column.key === 'id' || column.key.endsWith('_id') ? 'font-mono text-[10px]' : '',
                ]"
              >
                <StatusMark
                  v-if="column.kind === 'status'"
                  :value="String(row[column.key] ?? '')"
                />
                <StatusMark
                  v-else-if="column.kind === 'revoked-status'"
                  :value="row[column.key] ? 'revoked' : 'active'"
                />
                <template v-else>{{ cellValue(row, column) }}</template>
              </td>
              <td v-if="rowActions" class="border-b border-line px-3 py-2 text-right">
                <slot name="row-action" :row="row" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <DataState v-else kind="empty" :message="`No ${title.toLowerCase()} found.`" />
    </section>
  </div>
</template>
