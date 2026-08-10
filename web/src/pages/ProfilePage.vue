<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";
import { computed } from "vue";

import { apiRequest, type Schemas } from "../api/client";
import { useAuth } from "../auth/useAuth";
import DataState from "../components/DataState.vue";
import PageHeader from "../components/PageHeader.vue";

const { permissions: cachedPermissionsSet } = useAuth();
const cachedPermissions = computed(() => Array.from(cachedPermissionsSet.value));

const profile = useQuery({
  queryKey: ["profile"],
  queryFn: () => apiRequest<Schemas["MeOut"]>("/admin/api/v1/auth/me"),
});
const profilePermissions = useQuery({
  queryKey: ["profile-permissions"],
  queryFn: () => apiRequest<Schemas["PermissionsOut"]>("/admin/api/v1/auth/permissions"),
});
const loading = computed(() => profile.isLoading.value || profilePermissions.isLoading.value);
const error = computed(() => profile.error.value || profilePermissions.error.value);
</script>

<template>
  <DataState v-if="loading" />
  <DataState
    v-else-if="error"
    kind="error"
    :message="error.message"
    retry
    @retry="() => { profile.refetch(); profilePermissions.refetch(); }"
  />
  <div v-else>
    <PageHeader
      title="Profile"
      description="Read-only account details for the signed-in operator."
    />
    <section class="grid gap-3 overflow-hidden rounded-md border border-line bg-white p-5 text-[12px]">
      <div><strong class="text-[11px] text-muted">User ID</strong><p>{{ profile.data.value?.id }}</p></div>
      <div><strong class="text-[11px] text-muted">Full name</strong><p>{{ profile.data.value?.full_name || "-" }}</p></div>
      <div><strong class="text-[11px] text-muted">Email</strong><p>{{ profile.data.value?.email }}</p></div>
      <div><strong class="text-[11px] text-muted">Status</strong><p>{{ profile.data.value?.status }}</p></div>
      <div><strong class="text-[11px] text-muted">Role ID</strong><p>{{ profile.data.value?.role_id || "-" }}</p></div>
      <div><strong class="text-[11px] text-muted">Tenant ID</strong><p>{{ profile.data.value?.tenant_id }}</p></div>
      <div>
        <strong class="text-[11px] text-muted">Permissions</strong>
        <ul class="mt-1 list-disc pl-5">
          <li v-for="permission in cachedPermissions" :key="permission">{{ permission }}</li>
          <li v-if="!cachedPermissions.length">No cached permission keys.</li>
        </ul>
      </div>
      <div>
        <strong class="text-[11px] text-muted">Server permissions endpoint</strong>
        <ul v-if="profilePermissions.data.value?.permissions.length" class="mt-1 list-disc pl-5">
          <li v-for="permission in profilePermissions.data.value.permissions" :key="permission">{{ permission }}</li>
        </ul>
        <p v-else class="mt-1">No permission entries returned.</p>
      </div>
    </section>
  </div>
</template>
