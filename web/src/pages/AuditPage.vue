<script setup lang="ts">
import ResourcePage, { type ResourceColumn } from "../components/ResourcePage.vue";

const columns: ResourceColumn[] = [
  { key: "created_at", label: "Time" },
  { key: "actor_user_id", label: "Actor" },
  { key: "action", label: "Action" },
  { key: "target_type", label: "Target" },
  { key: "target_id", label: "Target ID" },
];
</script>

<template>
  <ResourcePage
    title="Audit log"
    description="Immutable operator activity with request correlation."
    endpoint="/admin/api/v1/audit"
    :columns="columns"
  />
</template>
