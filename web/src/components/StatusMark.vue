<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ value: string }>();

const tone = computed(() => {
  const normalized = props.value.toLowerCase();
  if (
    normalized.includes("fail") ||
    normalized.includes("offline") ||
    normalized.includes("dead") ||
    normalized.includes("reversed") ||
    normalized.includes("revoked")
  ) {
    return "danger";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("review") ||
    normalized.includes("retry") ||
    normalized.includes("leased")
  ) {
    return "warning";
  }
  return "success";
});

const tones = {
  success: "text-success before:bg-success",
  warning: "text-warning before:bg-warning",
  danger: "text-danger before:bg-danger",
};
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 whitespace-nowrap text-[11px] capitalize before:size-1.5 before:shrink-0 before:rounded-full"
    :class="tones[tone]"
  >
    {{ value.replaceAll("_", " ") }}
  </span>
</template>
