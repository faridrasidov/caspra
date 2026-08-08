import { createRouter, createWebHistory } from "vue-router";

import AppShell from "./components/AppShell.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", component: () => import("./pages/OverviewPage.vue") },
        { path: "customers", component: () => import("./pages/CustomersPage.vue") },
        { path: "cards", component: () => import("./pages/CardsPage.vue") },
        { path: "wallets", component: () => import("./pages/WalletsPage.vue") },
        {
          path: "transactions",
          component: () => import("./pages/TransactionsPage.vue"),
        },
        { path: "devices", component: () => import("./pages/DevicesPage.vue") },
        { path: "offline", component: () => import("./pages/OfflinePage.vue") },
        { path: "webhooks", component: () => import("./pages/WebhooksPage.vue") },
        { path: "api-keys", component: () => import("./pages/ApiKeysPage.vue") },
        { path: "audit", component: () => import("./pages/AuditPage.vue") },
        { path: "settings", component: () => import("./pages/SettingsPage.vue") },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
