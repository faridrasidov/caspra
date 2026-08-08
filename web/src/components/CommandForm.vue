<script setup lang="ts">
import UiButton from "./UiButton.vue";

defineProps<{
  submitLabel: string;
  submitting: boolean;
}>();

defineEmits<{
  submit: [event: Event];
  cancel: [];
}>();
</script>

<template>
  <form class="flex min-h-full flex-col" @submit.prevent="$emit('submit', $event)">
    <div class="grid flex-1 content-start gap-4 px-[18px] py-5">
      <slot />
    </div>
    <footer class="flex shrink-0 justify-end gap-2 border-t border-line bg-white px-[18px] py-3.5">
      <UiButton type="button" variant="secondary" @click="$emit('cancel')">Cancel</UiButton>
      <UiButton type="submit" :disabled="submitting">
        {{ submitting ? "Working..." : submitLabel }}
      </UiButton>
    </footer>
  </form>
</template>
