<script setup lang="ts">
import { RiLogoutBoxRLine, RiSaveLine } from "@remixicon/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { ref, watch } from "vue";

import { apiRequest, type Schemas } from "../api/client";
import { useAuth } from "../auth/useAuth";
import DataState from "../components/DataState.vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";

const queryClient = useQueryClient();
const { logout } = useAuth();
const settings = useQuery({
  queryKey: ["org-settings"],
  queryFn: () => apiRequest<Schemas["OrgSettingsOut"]>("/admin/api/v1/org/settings"),
});
const timezone = ref("UTC");
watch(settings.data, (value) => {
  if (value) timezone.value = value.timezone;
});
const save = useMutation({
  mutationFn: () =>
    apiRequest("/admin/api/v1/org/settings", {
      method: "PATCH",
      body: JSON.stringify({ timezone: timezone.value }),
    }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["org-settings"] }),
});
const revokeSessions = useMutation({
  mutationFn: () =>
    apiRequest<void>("/admin/api/v1/auth/sessions/revoke-all", { method: "POST" }),
  onSuccess: logout,
});
</script>

<template>
  <DataState v-if="settings.isLoading.value" />
  <DataState
    v-else-if="settings.error.value"
    kind="error"
    :message="settings.error.value.message"
  />
  <div v-else>
    <PageHeader
      title="Settings"
      description="Organization defaults and operator session controls."
    />
    <form class="overflow-hidden rounded-md border border-line bg-white" @submit.prevent="save.mutate()">
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">Regional settings</h2>
        <FormField label="Timezone"><input v-model="timezone" required /></FormField>
      </section>
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">Session security</h2>
        <div><UiButton :icon="RiLogoutBoxRLine" type="button" variant="secondary" :disabled="revokeSessions.isPending.value" @click="revokeSessions.mutate()">Revoke all sessions</UiButton></div>
      </section>
      <p v-if="save.error.value || revokeSessions.error.value" class="px-5 pt-4 text-[12px] text-danger" role="alert">{{ save.error.value?.message ?? revokeSessions.error.value?.message }}</p>
      <footer class="flex justify-end bg-subtle px-5 py-3.5">
        <UiButton :icon="RiSaveLine" type="submit" :disabled="save.isPending.value">{{ save.isPending.value ? "Saving..." : "Save settings" }}</UiButton>
      </footer>
    </form>
  </div>
</template>
