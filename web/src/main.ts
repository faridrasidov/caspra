import { VueQueryPlugin } from "@tanstack/vue-query";
import { createApp } from "vue";

import App from "./App.vue";
import "./app.css";
import { queryClient } from "./api/queryClient";
import { router } from "./router";

createApp(App).use(VueQueryPlugin, { queryClient }).use(router).mount("#root");
