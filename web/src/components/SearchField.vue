<script setup lang="ts">
import { RiSearchLine } from "@remixicon/vue";

withDefaults(
  defineProps<{
    modelValue: string;
    placeholder?: string;
  }>(),
  { placeholder: "Search" },
);

defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <label class="flex h-9 w-[260px] items-center gap-2 rounded-md border border-line bg-white px-3 text-muted focus-within:border-primary max-[760px]:w-full">
    <RiSearchLine aria-hidden="true" class="size-4 shrink-0" />
    <span class="sr-only">{{ placeholder }}</span>
    <input
      :value="modelValue"
      :placeholder="placeholder"
      class="min-w-0 flex-1 border-0 bg-transparent text-[12px] text-ink outline-none placeholder:text-muted"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </label>
</template>
