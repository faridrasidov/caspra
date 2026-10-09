import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";
import pluginVue from "eslint-plugin-vue";

export default defineConfigWithVueTs(
  {
    name: "app/files-to-lint",
    files: ["**/*.{ts,mts,vue}"],
  },
  {
    name: "app/files-to-ignore",
    ignores: ["dist/**", "src/api/schema.d.ts", "test-results/**", "playwright-report/**"],
  },
  pluginVue.configs["flat/essential"],
  vueTsConfigs.recommended,
);
