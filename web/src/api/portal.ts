import { ApiError } from "./client";

let token: string | null = null;
let refreshPromise: Promise<boolean> | null = null;
const prefix = "/customer/api/v1";

export function setPortalToken(value: string | null) { token = value; }

export async function refreshPortal() {
  if (!refreshPromise) refreshPromise = fetch(`${prefix}/auth/refresh`, { method: "POST", credentials: "include" })
    .then(async response => { if (!response.ok) { token = null; return false; } token = (await response.json()).access_token; return true; })
    .catch(() => false).finally(() => { refreshPromise = null; });
  return refreshPromise;
}

export async function portalRequest<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${prefix}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && retry && !path.startsWith("/auth/") && await refreshPortal()) return portalRequest<T>(path, init, false);
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, body.code ?? "request_failed", body.detail ?? "Request failed");
  return body as T;
}
