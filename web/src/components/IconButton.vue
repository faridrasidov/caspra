<script setup lang="ts">
import type { Component } from "vue";

defineProps<{
  label: string;
  icon: Component;
}>();
</script>

<template>
  <button
    :aria-label="label"
    :title="label"
    class="inline-grid size-9 shrink-0 place-items-center rounded-md border border-line bg-white text-muted transition-colors hover:bg-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-45"
  >
    <component :is="icon" aria-hidden="true" class="size-[18px]" />
  </button>
</template>
