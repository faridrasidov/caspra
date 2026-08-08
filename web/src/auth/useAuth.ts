import { readonly, ref } from "vue";

import {
  apiRequest,
  refreshAccessToken,
  setAccessToken,
  type MeOut,
  type Schemas,
  type TokenOut,
} from "../api/client";

const loading = ref(true);
const user = ref<MeOut | null>(null);
const permissions = ref<Set<string>>(new Set());
let initializePromise: Promise<void> | null = null;

export async function reloadIdentity() {
  const [profile, permissionResult] = await Promise.all([
    apiRequest<MeOut>("/admin/api/v1/auth/me"),
    apiRequest<Schemas["PermissionsOut"]>("/admin/api/v1/auth/permissions"),
  ]);
  user.value = profile;
  permissions.value = new Set(permissionResult.permissions);
}

export function initializeAuth() {
  if (!initializePromise) {
    initializePromise = refreshAccessToken()
      .then(async (token) => {
        if (token) await reloadIdentity();
      })
      .catch(() => undefined)
      .finally(() => {
        loading.value = false;
      });
  }
  return initializePromise;
}

export async function login(email: string, password: string) {
  const tokens = await apiRequest<TokenOut>(
    "/admin/api/v1/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    false,
  );
  setAccessToken(tokens.access_token);
  await reloadIdentity();
}

export async function logout() {
  try {
    await apiRequest<void>("/admin/api/v1/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
    user.value = null;
    permissions.value = new Set();
  }
}

export function useAuth() {
  return {
    loading: readonly(loading),
    user: readonly(user),
    permissions: readonly(permissions),
    login,
    logout,
    reloadIdentity,
  };
}
