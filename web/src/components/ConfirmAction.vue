<script setup lang="ts">
import CommandForm from "./CommandForm.vue";
import FormField from "./FormField.vue";

withDefaults(
  defineProps<{
    submitLabel: string;
    submitting: boolean;
    message?: string;
    requireReason?: boolean;
    error?: string;
  }>(),
  { requireReason: true },
);

const reason = defineModel<string>("reason", { default: "" });

defineEmits<{
  submit: [];
  cancel: [];
}>();
</script>

<template>
  <CommandForm
    :submit-label="submitLabel"
    :submitting="submitting"
    @submit="$emit('submit')"
    @cancel="$emit('cancel')"
  >
    <p v-if="message" class="text-[12px] text-muted">{{ message }}</p>
    <FormField v-if="requireReason" label="Reason required">
      <textarea v-model="reason" minlength="3" required />
    </FormField>
    <p v-if="error" class="text-[12px] text-danger" role="alert">{{ error }}</p>
  </CommandForm>
</template>
