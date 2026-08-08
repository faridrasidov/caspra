<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <header class="mb-5 flex min-h-14 items-start justify-between gap-5 max-[760px]:flex-col">
    <div>
      <h1 class="text-xl font-bold tracking-[-0.02em] text-ink">{{ title }}</h1>
      <p v-if="description" class="mt-1 text-[12px] text-muted">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2 max-[760px]:w-full max-[760px]:[&>*]:w-full">
      <slot name="actions" />
    </div>
  </header>
</template>
