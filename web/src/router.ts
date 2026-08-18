import { createRouter, createWebHistory } from "vue-router";

import { initializeAuth, useAuth } from "./auth/useAuth";
import AppShell from "./components/AppShell.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", component: () => import("./pages/OverviewPage.vue") },
        {
          path: "customers",
          component: () => import("./pages/CustomersPage.vue"),
          meta: { permission: "customers:read" },
        },
        {
          path: "cards",
          component: () => import("./pages/CardsPage.vue"),
          meta: { permission: "cards:read" },
        },
        {
          path: "wallets",
          component: () => import("./pages/WalletsPage.vue"),
          meta: { permission: "wallets:read" },
        },
        {
          path: "transactions",
          component: () => import("./pages/TransactionsPage.vue"),
          meta: { permission: "transactions:read" },
        },
        {
          path: "devices",
          component: () => import("./pages/DevicesPage.vue"),
          meta: { permission: "devices:read" },
        },
        {
          path: "offline",
          component: () => import("./pages/OfflinePage.vue"),
          meta: { permission: "transactions:read" },
        },
        {
          path: "webhooks",
          component: () => import("./pages/WebhooksPage.vue"),
          meta: { permission: "integrations:manage" },
        },
        {
          path: "api-keys",
          component: () => import("./pages/ApiKeysPage.vue"),
          meta: { permission: "integrations:manage" },
        },
        {
          path: "audit",
          component: () => import("./pages/AuditPage.vue"),
          meta: { permission: "audit:read" },
        },
        {
          path: "settings",
          component: () => import("./pages/SettingsPage.vue"),
          meta: { permission: "settings:manage" },
        },
        { path: "notifications", component: () => import("./pages/NotificationsPage.vue") },
        { path: "profile", component: () => import("./pages/ProfilePage.vue") },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async (to) => {
  await initializeAuth();
  const permission = to.matched.find((record) => record.meta.permission)?.meta
    .permission as string | undefined;
  if (!permission) return true;
  const { user, permissions } = useAuth();
  if (!user.value) return true;
  if (!permissions.value.has(permission)) return { path: "/" };
  return true;
});
