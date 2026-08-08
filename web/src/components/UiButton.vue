<script setup lang="ts">
import type { Component } from "vue";

withDefaults(
  defineProps<{
    icon?: Component;
    variant?: "primary" | "secondary" | "danger" | "ghost";
  }>(),
  { variant: "primary" },
);

const variants = {
  primary: "border-primary bg-primary text-white hover:border-primary-hover hover:bg-primary-hover",
  secondary: "border-line-strong bg-white text-ink hover:bg-subtle",
  danger: "border-danger bg-danger text-white hover:brightness-95",
  ghost: "border-transparent bg-transparent text-muted hover:bg-subtle hover:text-ink",
};
</script>

<template>
  <button
    class="inline-flex min-h-9 items-center justify-center gap-2 rounded-md border px-3.5 text-[12px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-55"
    :class="variants[variant]"
  >
    <component :is="icon" v-if="icon" aria-hidden="true" class="size-4 shrink-0" />
    <slot />
  </button>
</template>
