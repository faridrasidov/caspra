<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import { computed, ref, watch } from "vue";

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
  labels?: Record<string, string>;
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
const page = ref(1);
const serverSearch = ref("");
let searchTimer: ReturnType<typeof setTimeout>;
watch(search, (value) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { serverSearch.value = value; page.value = 1; }, 250);
});
const resource = useQuery({
  refetchInterval: 15000,
  queryKey: computed(() => ["resource", props.endpoint, page.value, serverSearch.value]),
  queryFn: () => apiRequest<PaginatedResult>(`${props.endpoint}${props.endpoint.includes('?') ? '&' : '?'}page=${page.value}&limit=20&q=${encodeURIComponent(serverSearch.value)}`),
});
const rows = computed(() => resource.data.value?.items ?? []);

function cellValue(row: ResourceRecord, column: ResourceColumn) {
  if (column.labels) return column.labels[String(row[column.key])] ?? renderValue(row[column.key]);
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
  <div class="min-w-0">
    <PageHeader :title="title" :description="description">
      <template v-if="$slots.actions" #actions><slot name="actions" /></template>
    </PageHeader>
    <section class="min-w-0 overflow-hidden rounded-md border border-line bg-white">
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
      <footer class="flex items-center justify-between border-t border-line p-3 text-xs">
        <button class="rounded border border-line px-3 py-2 disabled:opacity-40" :disabled="page <= 1" @click="page--">Previous</button>
        <span>Page {{ page }} · {{ resource.data.value?.total ?? 0 }} records</span>
        <button class="rounded border border-line px-3 py-2 disabled:opacity-40" :disabled="page * 20 >= (resource.data.value?.total ?? 0)" @click="page++">Next</button>
      </footer>
    </section>
  </div>
</template>
