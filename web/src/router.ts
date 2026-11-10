import { createRouter, createWebHistory } from "vue-router";

import AppShell from "./components/AppShell.vue";
import { initializeAuth, staffHome, useAuth } from "./auth/useAuth";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/portal", component: () => import("./pages/PortalPage.vue") },
    {
      path: "/",
      component: AppShell,
      children: [
        { path: "", component: () => import("./pages/OverviewPage.vue"), meta: { permission: "reports:read" } },
        { path: "reports", component: () => import("./pages/ReportsPage.vue"), meta: { permission: "reports:read" } },
        { path: "machines", component: () => import("./pages/MachinesPage.vue"), meta: { permission: "machines:read" } },
        { path: "plays", component: () => import("./pages/PlaysPage.vue"), meta: { permission: "plays:read" } },
        { path: "cashier", component: () => import("./pages/CashierPage.vue"), meta: { permission: "shifts:operate" } },
        { path: "pricing", component: () => import("./pages/PricingPage.vue"), meta: { permission: "pricing:manage" } },
        { path: "families", component: () => import("./pages/FamiliesPage.vue"), meta: { permission: "family:manage" } },
        { path: "alerts", component: () => import("./pages/AlertsPage.vue"), meta: { permission: "alerts:read" } },
        { path: "staff", component: () => import("./pages/StaffPage.vue"), meta: { permission: "users:manage" } },
        { path: "customers/:id", component: () => import("./pages/CustomerDetailPage.vue"), meta: { permission: "customers:read" } },
        { path: "no-access", component: () => import("./pages/NoAccessPage.vue") },
        { path: "customers", component: () => import("./pages/CustomersPage.vue"), meta: { permission: "customers:read" } },
        { path: "cards", component: () => import("./pages/CardsPage.vue"), meta: { permission: "cards:read" } },
        { path: "wallets", component: () => import("./pages/WalletsPage.vue"), meta: { permission: "wallets:read" } },
        {
          path: "transactions",
          meta: { permission: "transactions:read" },
          component: () => import("./pages/TransactionsPage.vue"),
        },
        { path: "devices", component: () => import("./pages/DevicesPage.vue"), meta: { permission: "devices:read" } },
        { path: "offline", component: () => import("./pages/OfflinePage.vue"), meta: { permission: "audit:read" } },
        { path: "webhooks", component: () => import("./pages/WebhooksPage.vue"), meta: { permission: "integrations:manage" } },
        { path: "api-keys", component: () => import("./pages/ApiKeysPage.vue"), meta: { permission: "integrations:manage" } },
        { path: "audit", component: () => import("./pages/AuditPage.vue"), meta: { permission: "audit:read" } },
        { path: "settings", component: () => import("./pages/SettingsPage.vue"), meta: { permission: "settings:manage" } },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async to => {
  if (to.path.startsWith("/portal")) return true;
  await initializeAuth();
  const { user, permissions } = useAuth();
  const required = to.meta.permission;
  if (user.value && typeof required === "string" && !permissions.value.has(required)) return staffHome();
  return true;
});
