<script setup lang="ts">
import { RiLoader4Line } from "@remixicon/vue";

import { useAuth } from "./auth/useAuth";
import { useRoute } from "vue-router";
import LoginPage from "./pages/LoginPage.vue";

const { loading, user } = useAuth();
const route = useRoute();
</script>

<template>
  <RouterView v-if="route.path.startsWith('/portal')" />
  <div
    v-else-if="loading"
    class="grid min-h-screen place-items-center bg-subtle text-sm font-semibold text-muted"
    role="status"
  >
    <span class="flex items-center gap-2.5">
      <RiLoader4Line aria-hidden="true" class="size-5 animate-spin" />
      Opening Caspra
    </span>
  </div>
  <LoginPage v-else-if="!user" />
  <RouterView v-else />
</template>
