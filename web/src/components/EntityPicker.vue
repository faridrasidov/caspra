<script setup lang="ts">
import { useQuery } from "@tanstack/vue-query";

import { apiRequest } from "../api/client";
import FormField from "./FormField.vue";

type Option = { id: string } & Record<string, unknown>;

const props = defineProps<{
  modelValue: string;
  label: string;
  hint?: string;
  endpoint: string;
  optionLabel: (item: Option) => string;
  required?: boolean;
  allowEmpty?: boolean;
  emptyLabel?: string;
}>();

defineEmits<{ "update:modelValue": [value: string] }>();

const list = useQuery({
  queryKey: ["picker", props.endpoint],
  queryFn: () =>
    apiRequest<{ items: Option[] }>(`${props.endpoint}?page=1&limit=100`),
});
</script>

<template>
  <FormField :label="label" :hint="hint">
    <select
      :value="modelValue"
      :required="required"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option value="">{{ emptyLabel ?? (allowEmpty ? "None" : "Select") }}</option>
      <option v-for="item in list.data.value?.items ?? []" :key="item.id" :value="item.id">
        {{ optionLabel(item) }}
      </option>
    </select>
  </FormField>
</template>
