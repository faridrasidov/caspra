import { defineConfig, loadEnv } from "vite";
import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => ({
  plugins: [
    // The published icon barrel lacks pure annotations on component factories.
    // Mark only those factories so unused icons leave the production bundle.
    {
      name: "remix-component-purity",
      enforce: "pre",
      transform(code, id) {
        if (!id.replace(/\\/g, "/").endsWith("/@remixicon/vue/index.mjs")) return;
        const factory = code.match(/defineComponent as (\w+)/)?.[1];
        if (!factory) throw new Error("Remix Icon component factory changed; review bundle optimization");
        return code.replace(new RegExp(`\\b${factory}\\(\\{name:"Ri`, "g"), `/*#__PURE__*/${factory}({name:"Ri`);
      },
    },
    vue(), tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      "/admin/api": loadEnv(mode, fileURLToPath(new URL(".", import.meta.url)), "CASPRA_").CASPRA_API_TARGET || "http://127.0.0.1:8000",
      "/customer/api": loadEnv(mode, fileURLToPath(new URL(".", import.meta.url)), "CASPRA_").CASPRA_API_TARGET || "http://127.0.0.1:8000",
      "/api": loadEnv(mode, fileURLToPath(new URL(".", import.meta.url)), "CASPRA_").CASPRA_API_TARGET || "http://127.0.0.1:8000",
    },
  },
}));
