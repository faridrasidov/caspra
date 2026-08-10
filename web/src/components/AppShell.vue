<script setup lang="ts">
import {
  RiArrowDownSLine,
  RiBankCardLine,
  RiBuilding2Line,
  RiCloseLine,
  RiDashboardLine,
  RiFileList3Line,
  RiGroupLine,
  RiHistoryLine,
  RiKey2Line,
  RiMenuLine,
  RiNotificationLine,
  RiRfidLine,
  RiSettings3Line,
  RiWallet3Line,
  RiWebhookLine,
  RiWifiOffLine,
} from "@remixicon/vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { useAuth } from "../auth/useAuth";
import IconButton from "./IconButton.vue";

const navigation = [
  { to: "/", label: "Overview", icon: RiDashboardLine },
  { to: "/customers", label: "Customers", icon: RiGroupLine, permission: "customers:read" },
  { to: "/cards", label: "Cards", icon: RiBankCardLine, permission: "cards:read" },
  { to: "/wallets", label: "Wallets", icon: RiWallet3Line, permission: "wallets:read" },
  {
    to: "/transactions",
    label: "Transactions",
    icon: RiHistoryLine,
    permission: "transactions:read",
  },
  { to: "/devices", label: "Devices", icon: RiRfidLine, permission: "devices:read" },
  {
    to: "/offline",
    label: "Offline review",
    icon: RiWifiOffLine,
    permission: "transactions:read",
  },
  {
    to: "/webhooks",
    label: "Webhooks",
    icon: RiWebhookLine,
    permission: "integrations:manage",
  },
  {
    to: "/api-keys",
    label: "API keys",
    icon: RiKey2Line,
    permission: "integrations:manage",
  },
  { to: "/audit", label: "Audit log", icon: RiFileList3Line, permission: "audit:read" },
  {
    to: "/settings",
    label: "Settings",
    icon: RiSettings3Line,
    permission: "settings:manage",
  },
];

const route = useRoute();
const { user, permissions, logout } = useAuth();
const mobileNav = ref(false);
const userMenuOpen = ref(false);
const userMenuButtonRef = ref<HTMLButtonElement | null>(null);
const userMenuRef = ref<HTMLElement | null>(null);
const current = computed(
  () => {
    const direct = navigation.find((item) =>
      item.to === "/" ? route.path === "/" : route.path.startsWith(item.to),
    );
    if (direct) return direct;
    if (route.path.startsWith("/settings")) return navigation.find((item) => item.to === "/settings") ?? { to: "/settings", label: "Settings", icon: RiSettings3Line };
    if (route.path === "/notifications") {
      return { to: "/notifications", label: "Notifications", icon: RiNotificationLine };
    }
    if (route.path === "/profile") {
      return { to: "/profile", label: "Profile", icon: RiBuilding2Line };
    }
    return { to: route.path, label: "Overview", icon: RiDashboardLine };
  },
);
const visibleNavigation = computed(() =>
  navigation.filter((item) => !item.permission || permissions.value.has(item.permission)),
);

const closeUserMenu = () => {
  userMenuOpen.value = false;
};

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value;
}

function closeMenuAndLogout() {
  closeUserMenu();
  logout();
}

function handleDocumentPointerDown(event: MouseEvent) {
  if (!userMenuOpen.value) return;
  const target = event.target as Node | null;
  if (!target) return;
  if (userMenuButtonRef.value?.contains(target)) return;
  if (userMenuRef.value?.contains(target)) return;
  closeUserMenu();
}

function handleDocumentKeyDown(event: KeyboardEvent) {
  if (event.key === "Escape") closeUserMenu();
}

onMounted(() => {
  document.addEventListener("pointerdown", handleDocumentPointerDown);
  document.addEventListener("keydown", handleDocumentKeyDown);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointerDown);
  document.removeEventListener("keydown", handleDocumentKeyDown);
});

watch(
  () => route.path,
  () => {
    closeUserMenu();
  },
);
</script>

<template>
  <div class="min-h-screen bg-subtle md:grid md:grid-cols-[216px_minmax(0,1fr)]">
    <button
      v-if="mobileNav"
      class="fixed inset-0 z-30 border-0 bg-black/25 md:hidden"
      aria-label="Close navigation"
      @click="mobileNav = false"
    />
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-[min(280px,86vw)] -translate-x-full flex-col bg-sidebar text-white transition-transform duration-200 md:sticky md:top-0 md:h-screen md:w-auto md:translate-x-0"
      :class="mobileNav ? 'translate-x-0 shadow-[10px_0_30px_rgb(20_24_28/24%)]' : ''"
    >
      <div class="flex h-16 shrink-0 items-center gap-2.5 px-[18px] text-[15px] font-extrabold tracking-[0.04em]">
        <span class="grid size-7 place-items-center rounded-md bg-primary text-[13px]" aria-hidden="true">C</span>
        <span>CASPRA</span>
        <IconButton
          label="Close navigation"
          :icon="RiCloseLine"
          class="ml-auto border-sidebar-raised bg-transparent text-white md:hidden"
          @click="mobileNav = false"
        />
      </div>
      <nav class="grid gap-0.5 px-2.5 py-3" aria-label="Primary navigation">
        <RouterLink
          v-for="item in visibleNavigation"
          :key="item.to"
          :to="item.to"
          class="flex h-10 items-center gap-3 rounded-md border-l-[3px] border-transparent px-2.5 text-[12px] font-semibold text-[#d8dde1] transition-colors hover:bg-sidebar-raised hover:text-white"
          active-class="!border-primary !bg-sidebar-raised !text-white"
          :exact-active-class="item.to === '/' ? '!border-primary !bg-sidebar-raised !text-white' : ''"
          @click="mobileNav = false"
        >
          <component :is="item.icon" aria-hidden="true" class="size-[19px] shrink-0" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="mt-auto flex items-center gap-2 border-t border-sidebar-raised px-[18px] py-5 text-[10px] text-[#d8dde1]">
        <span class="size-2 rounded-full bg-[#21b34b]" aria-hidden="true" />
        All systems operational
      </div>
    </aside>

    <div class="min-w-0">
      <header class="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-line bg-white px-[22px] max-[760px]:h-14 max-[760px]:px-2.5">
        <div class="flex items-center gap-3">
          <span class="hidden max-[760px]:block">
            <IconButton
              label="Open navigation"
              :icon="RiMenuLine"
              @click="mobileNav = true"
            />
          </span>
          <h2 class="text-lg font-bold tracking-[-0.02em] max-[760px]:text-base">{{ current.label }}</h2>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-[11px] text-ink max-[760px]:hidden"
            title="Current organization"
          >
            <RiBuilding2Line aria-hidden="true" class="size-4" />
            <span>Primary venue</span>
            <RiArrowDownSLine aria-hidden="true" class="size-[15px]" />
          </button>
          <RouterLink
            to="/notifications"
            aria-label="Notifications"
            class="inline-grid size-9 shrink-0 place-items-center rounded-md border border-line bg-white text-muted transition-colors hover:bg-subtle hover:text-ink max-[760px]:hidden"
          >
            <RiNotificationLine aria-hidden="true" class="size-[18px]" />
          </RouterLink>
          <div class="relative">
            <button
              ref="userMenuButtonRef"
              class="flex h-10 min-w-[210px] items-center gap-2.5 rounded-md border border-line bg-white px-2.5 text-left max-[760px]:min-w-0 max-[760px]:border-0 max-[760px]:px-1"
              @click="toggleUserMenu"
            >
              <span class="grid size-7 shrink-0 place-items-center rounded-full bg-[#45515c] text-[11px] font-bold text-white">
                {{ user?.email.slice(0, 1).toUpperCase() }}
              </span>
              <span class="grid min-w-0 flex-1 max-[760px]:hidden">
                <strong class="truncate text-[11px] leading-4">{{ user?.full_name || "Operator" }}</strong>
                <small class="truncate text-[9px] leading-3 text-muted">{{ user?.email }}</small>
              </span>
              <RiArrowDownSLine aria-hidden="true" class="size-[15px] max-[760px]:hidden" />
            </button>
            <div
              v-if="userMenuOpen"
              ref="userMenuRef"
              class="absolute right-0 top-full z-30 mt-2 w-52 rounded-md border border-line bg-white p-1 shadow-[0_10px_28px_rgb(8_24_38/18%)]"
            >
              <RouterLink
                to="/profile"
                class="block rounded-md px-2.5 py-2 text-left text-[11px] font-semibold text-ink hover:bg-subtle"
                @click="closeUserMenu"
              >
                Profile
              </RouterLink>
              <RouterLink
                to="/settings"
                class="block rounded-md px-2.5 py-2 text-left text-[11px] font-semibold text-ink hover:bg-subtle"
                @click="closeUserMenu"
              >
                Settings
              </RouterLink>
              <RouterLink
                to="/notifications"
                class="block rounded-md px-2.5 py-2 text-left text-[11px] font-semibold text-ink hover:bg-subtle"
                @click="closeUserMenu"
              >
                Notifications
              </RouterLink>
              <button
                class="block w-full rounded-md px-2.5 py-2 text-left text-[11px] font-semibold text-danger transition-colors hover:bg-subtle"
                @click="closeMenuAndLogout"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>
      <main class="min-h-[calc(100vh-64px)] p-[18px_22px_32px] max-[760px]:min-h-[calc(100vh-56px)] max-[760px]:p-4 max-[760px]:px-3">
        <RouterView />
      </main>
    </div>
  </div>
</template>
