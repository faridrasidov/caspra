<script setup lang="ts">
defineProps<{
  label: string;
  hint?: string;
}>();
</script>

<template>
  <label
    class="grid gap-1.5 text-[12px] font-semibold text-ink [&_input]:h-10 [&_input]:rounded-md [&_input]:border [&_input]:border-line-strong [&_input]:bg-white [&_input]:px-3 [&_input]:font-normal [&_input]:outline-none [&_input]:focus:border-primary [&_select]:h-10 [&_select]:rounded-md [&_select]:border [&_select]:border-line-strong [&_select]:bg-white [&_select]:px-3 [&_select]:font-normal [&_select]:outline-none [&_select]:focus:border-primary [&_textarea]:min-h-24 [&_textarea]:resize-y [&_textarea]:rounded-md [&_textarea]:border [&_textarea]:border-line-strong [&_textarea]:bg-white [&_textarea]:p-3 [&_textarea]:font-normal [&_textarea]:outline-none [&_textarea]:focus:border-primary"
  >
    <span>{{ label }}</span>
    <slot />
    <small v-if="hint" class="font-normal text-muted">{{ hint }}</small>
  </label>
</template>
