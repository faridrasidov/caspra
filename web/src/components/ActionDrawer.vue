<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import AppDrawer from "./AppDrawer.vue";
import CommandForm from "./CommandForm.vue";
import FormField from "./FormField.vue";
import { toMinorUnits } from "../utils/format";

export type ActionField = {
  key: string;
  label: string;
  kind?: "text" | "number" | "money" | "select" | "email" | "password" | "textarea";
  required?: boolean;
  signed?: boolean;
  value?: string | number;
  options?: { value: string; label: string }[];
};
const props = defineProps<{ open: boolean; title: string; fields: ActionField[]; pending?: boolean; error?: string; currency?: string; submitLabel?: string }>();
const emit = defineEmits<{ close: []; submit: [values: Record<string, string | number | null>, key: string] }>();
const values = reactive<Record<string, string>>({});
const validation = ref("");
const operationKey = ref(crypto.randomUUID());
watch(() => props.open, (open) => {
  if (!open) return;
  Object.keys(values).forEach((key) => delete values[key]);
  props.fields.forEach((field) => { values[field.key] = String(field.value ?? ""); });
  validation.value = "";
  operationKey.value = crypto.randomUUID();
});
watch(values, () => { operationKey.value = crypto.randomUUID(); });
function submit() {
  try {
    const result: Record<string, string | number | null> = {};
    for (const field of props.fields) {
      const value = values[field.key]?.trim() ?? "";
      if (!value && field.required !== false) throw new Error(`${field.label} is required`);
      result[field.key] = !value ? null : field.kind === "money" ? (field.signed && value.startsWith('-') ? -1 : 1) * toMinorUnits(field.signed ? value.replace(/^-/, '') : value, String(values.currency || props.currency || "USD")) : field.kind === "number" ? Number(value) : value;
    }
    validation.value = "";
    emit("submit", result, operationKey.value);
  } catch (error) { validation.value = (error as Error).message; }
}
</script>

<template>
  <AppDrawer :open="open" :title="title" @close="emit('close')">
    <CommandForm :submit-label="submitLabel ?? 'Save'" :submitting="Boolean(pending)" @submit="submit" @cancel="emit('close')">
      <FormField v-for="field in fields" :key="field.key" :label="field.label">
        <select v-if="field.kind === 'select'" v-model="values[field.key]" :aria-label="field.label" :disabled="pending" :required="field.required !== false">
          <option value="" disabled>Select {{ field.label.toLowerCase() }}</option>
          <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
        <textarea v-else-if="field.kind === 'textarea'" v-model="values[field.key]" :aria-label="field.label" :disabled="pending" :required="field.required !== false" rows="3" />
        <input v-else v-model="values[field.key]" :aria-label="field.label" :disabled="pending" :type="field.kind === 'email' ? 'email' : field.kind === 'password' ? 'password' : field.kind === 'number' ? 'number' : 'text'" :inputmode="field.kind === 'money' ? 'decimal' : undefined" :required="field.required !== false" />
      </FormField>
      <p v-if="validation || error" role="alert" class="text-sm text-danger">{{ validation || error }}</p>
    </CommandForm>
  </AppDrawer>
</template>
