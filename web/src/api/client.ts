import type { components } from "./schema";

export type Schemas = components["schemas"];
export type TokenOut = Schemas["TokenOut"];
export type MeOut = Schemas["MeOut"];
export type TransactionOut = Schemas["TransactionOut"];
export type TransactionStatsOut = Schemas["TransactionStatsOut"];
export type DeviceOut = Schemas["DeviceOut"];
export type OfflineReviewItemOut = Schemas["OfflineReviewItemOut"];
export type WebhookDeliveryOut = Schemas["WebhookDeliveryOut"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

async function decodeResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body.code ?? `http_${response.status}`,
      body.detail ?? "The request could not be completed",
    );
  }
  return body as T;
}

export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = fetch("/admin/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    })
      .then((response) => decodeResponse<TokenOut>(response))
      .then((tokens) => {
        setAccessToken(tokens.access_token);
        return tokens.access_token;
      })
      .catch(() => {
        setAccessToken(null);
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });
  if (
    response.status === 401 &&
    retry &&
    !path.includes("/auth/login") &&
    !path.includes("/auth/refresh")
  ) {
    const token = await refreshAccessToken();
    if (token) return apiRequest<T>(path, init, false);
  }
  return decodeResponse<T>(response);
}

export function toQuery(
  values: Record<string, string | number | boolean | undefined>,
) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const rendered = query.toString();
  return rendered ? `?${rendered}` : "";
}
