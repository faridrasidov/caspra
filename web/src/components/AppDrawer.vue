<script setup lang="ts">
import { RiCloseLine } from "@remixicon/vue";

import IconButton from "./IconButton.vue";

defineProps<{
  title: string;
  open: boolean;
}>();

defineEmits<{ close: [] }>();
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex justify-end">
      <button
        class="absolute inset-0 border-0 bg-black/25"
        aria-label="Close dialog"
        @click="$emit('close')"
      />
      <section
        class="relative z-10 flex h-full w-full max-w-[380px] animate-[drawer-in_180ms_ease-out] flex-col border-l border-line bg-white shadow-panel"
        role="dialog"
        aria-modal="true"
      >
        <header class="flex h-16 shrink-0 items-center justify-between border-b border-line pl-[18px] pr-3.5">
          <h2 class="text-[15px] font-bold text-ink">{{ title }}</h2>
          <IconButton label="Close" :icon="RiCloseLine" @click="$emit('close')" />
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto">
          <slot />
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style>
@keyframes drawer-in {
  from {
    transform: translateX(100%);
  }
}
</style>
