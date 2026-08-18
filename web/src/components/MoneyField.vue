<script setup lang="ts">
import FormField from "./FormField.vue";

withDefaults(
  defineProps<{
    modelValue: string;
    label?: string;
    currency?: string;
    required?: boolean;
    min?: string;
  }>(),
  { label: "Amount", currency: "USD", required: true, min: "0.01" },
);

defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <FormField :label="label" :hint="currency">
    <input
      :value="modelValue"
      type="number"
      :min="min"
      step="0.01"
      :required="required"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </FormField>
</template>
