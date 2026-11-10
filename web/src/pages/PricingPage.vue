<script setup lang="ts">
import { computed, ref } from "vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { apiRequest } from "../api/client";
import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";
import ResourcePage, { type ResourceRecord } from "../components/ResourcePage.vue";
import UiButton from "../components/UiButton.vue";

const queryClient = useQueryClient();
const mode = ref<"package" | "schedule" | "disable-package" | "disable-schedule" | null>(null);
const selected = ref<ResourceRecord | null>(null);
const machineId = ref("");
const machines = useQuery({ queryKey: ["pricing-machines"], queryFn: () => apiRequest<{ items: { id: string; name: string; currency: string }[] }>("/admin/api/v1/machines?limit=100") });
const org = useQuery({ queryKey: ["org"], queryFn: () => apiRequest<{ default_currency: string }>("/admin/api/v1/org") });
const currency = computed(() => machines.data.value?.items.find(m => m.id === machineId.value)?.currency ?? org.data.value?.default_currency ?? "USD");
const fields = computed<ActionField[]>(() => {
  if (mode.value?.startsWith("disable")) return [{ key: "confirmation", label: "Type DISABLE to confirm" }];
  if (mode.value === "package") return [{ key: "name", label: "Package name" }, { key: "currency", label: "Currency", value: org.data.value?.default_currency ?? "USD" }, { key: "paid_minor", label: "Paid credit", kind: "money" }, { key: "bonus_minor", label: "Bonus credit", kind: "money", value: "0" }];
  return [{ key: "name", label: "Schedule name" }, { key: "weekday", label: "Weekday", kind: "select", options: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((label, index) => ({ value: String(index), label })) }, { key: "starts", label: "Starts at (HH:MM)", value: "14:00" }, { key: "ends", label: "Ends at (HH:MM)", value: "16:00" }, { key: "price_minor", label: `Promotional play price (${currency.value})`, kind: "money" }];
});
function minute(value: unknown) { const text = String(value); if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(text)) throw new Error("Use a time in HH:MM format"); const [hours, minutes] = text.split(":").map(Number); return hours! * 60 + minutes!; }
const save = useMutation({ mutationFn: async (values: Record<string, unknown>) => {
  const packageMode = mode.value?.includes("package");
  let path = `/admin/api/v1/${packageMode ? 'topup-packages' : 'pricing-schedules'}`;
  if (mode.value?.startsWith("disable")) { if (values.confirmation !== "DISABLE") throw new Error("Type DISABLE to confirm"); return apiRequest(`${path}/${selected.value?.id}`, { method: "DELETE" }); }
  const body = packageMode ? values : { name: values.name, machine_id: machineId.value, weekday: Number(values.weekday), start_minute: minute(values.starts), end_minute: minute(values.ends), price_minor: values.price_minor };
  return apiRequest(path, { method: "POST", body: JSON.stringify(body) });
}, onSuccess: async () => { mode.value = null; await queryClient.invalidateQueries({ queryKey: ["resource"] }); await queryClient.invalidateQueries({ queryKey: ["packages"] }); } });
function disable(kind: "package" | "schedule", row: ResourceRecord) { selected.value = row; mode.value = `disable-${kind}`; }
</script>
<template>
  <div class="grid gap-6">
    <ResourcePage title="Top-up packages" description="Paid credit and separate promotional credit. Packages are snapshotted on receipts." endpoint="/admin/api/v1/topup-packages" :columns="[{ key: 'name', label: 'Package' }, { key: 'paid_minor', label: 'Paid', kind: 'money' }, { key: 'bonus_minor', label: 'Bonus', kind: 'money' }, { key: 'active', label: 'Active' }]" row-actions>
      <template #actions><UiButton @click="mode = 'package'">Add package</UiButton></template>
      <template #row-action="{ row }"><UiButton v-if="row.active" variant="secondary" @click="disable('package', row)">Disable</UiButton></template>
    </ResourcePage>
    <div class="flex flex-wrap items-center gap-3 text-sm"><label for="pricing-machine">Machine for new schedule</label><select id="pricing-machine" v-model="machineId" class="rounded border border-line bg-white p-2"><option value="">Select machine</option><option v-for="machine in machines.data.value?.items" :key="machine.id" :value="machine.id">{{ machine.name }} · {{ machine.currency }}</option></select></div>
    <ResourcePage title="Happy-hour pricing" description="Weekly schedules follow the venue timezone. Overlapping schedules are rejected." endpoint="/admin/api/v1/pricing-schedules" :columns="[{ key: 'name', label: 'Schedule' }, { key: 'weekday_name', label: 'Weekday' }, { key: 'start_time', label: 'From' }, { key: 'end_time', label: 'Through' }, { key: 'price_minor', label: 'Play price', kind: 'money' }, { key: 'active', label: 'Active' }]" row-actions>
      <template #actions><UiButton :disabled="!machineId" @click="mode = 'schedule'">Add schedule</UiButton></template>
      <template #row-action="{ row }"><UiButton v-if="row.active" variant="secondary" @click="disable('schedule', row)">Disable</UiButton></template>
    </ResourcePage>
    <ActionDrawer :open="Boolean(mode)" :title="mode?.startsWith('disable') ? 'Disable future use' : mode === 'package' ? 'Add top-up package' : 'Add happy-hour schedule'" :fields="fields" :currency="currency" :pending="save.isPending.value" :error="save.error.value?.message" @close="mode = null" @submit="values => save.mutate(values)" />
  </div>
</template>
