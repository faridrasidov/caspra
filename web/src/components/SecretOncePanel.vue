<script setup lang="ts">
import UiButton from "./UiButton.vue";

const props = defineProps<{
  value: string;
  warning?: string;
}>();

const emit = defineEmits<{ close: [] }>();

async function copyAndClose() {
  await navigator.clipboard.writeText(props.value);
  emit("close");
}
</script>

<template>
  <div class="grid gap-4 p-5">
    <p class="text-[12px] text-muted">{{ warning ?? "This secret is shown once." }}</p>
    <code class="overflow-x-auto rounded-md border border-line bg-subtle p-3 font-mono text-[11px]">{{ value }}</code>
    <UiButton @click="copyAndClose">Copy and close</UiButton>
  </div>
</template>
