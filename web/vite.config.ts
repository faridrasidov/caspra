import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/admin/api": "https://api-caspra.xakep.ir/",
      "/api": "https://api-caspra.xakep.ir/",
    },
  },
});
