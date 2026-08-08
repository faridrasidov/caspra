import { VueQueryPlugin, type VueQueryPluginOptions } from "@tanstack/vue-query";
import { createApp } from "vue";

import App from "./App.vue";
import "./app.css";
import { initializeAuth } from "./auth/useAuth";
import { router } from "./router";

const queryOptions: VueQueryPluginOptions = {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  },
};

createApp(App).use(VueQueryPlugin, queryOptions).use(router).mount("#root");
void initializeAuth();
