<script setup lang="ts">
import {
  RiAlertLine,
  RiCheckLine,
  RiLoader4Line,
} from "@remixicon/vue";
import { computed } from "vue";

import UiButton from "./UiButton.vue";

const props = withDefaults(
  defineProps<{
    kind?: "loading" | "error" | "empty";
    message?: string;
    retry?: boolean;
  }>(),
  { kind: "loading", message: "Loading data", retry: false },
);

defineEmits<{ retry: [] }>();

const icon = computed(() => {
  if (props.kind === "error") return RiAlertLine;
  if (props.kind === "empty") return RiCheckLine;
  return RiLoader4Line;
});
</script>

<template>
  <div
    class="flex min-h-40 items-center justify-center gap-2.5 p-6 text-center text-[12px] text-muted"
    :class="kind === 'error' ? 'text-danger' : ''"
    :role="kind === 'error' ? 'alert' : kind === 'loading' ? 'status' : undefined"
  >
    <component
      :is="icon"
      aria-hidden="true"
      class="size-[22px] shrink-0"
      :class="kind === 'loading' ? 'animate-spin' : ''"
    />
    <span>{{ message }}</span>
    <UiButton v-if="kind === 'error' && retry" variant="secondary" @click="$emit('retry')">
      Retry
    </UiButton>
  </div>
</template>
