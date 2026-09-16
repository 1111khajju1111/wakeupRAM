/**
 * Thin fetch wrapper. The backend base URL is configuration-driven
 * (VITE_API_BASE_URL) — never hardcoded — so the same build works against
 * local dev, a staging Render deployment, or production.
 */
import { getAuthTokens, setAuthTokens, clearAuthTokens } from "./tokenStorage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions extends RequestInit {
  auth?: boolean; // attach Authorization header
}

async function request<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
  const { auth = true, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  finalHeaders.set("Content-Type", "application/json");

  if (auth) {
    const tokens = await getAuthTokens();
    if (tokens?.accessToken) {
      finalHeaders.set("Authorization", `Bearer ${tokens.accessToken}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...rest, headers: finalHeaders });

  // isRetry guards against infinite recursion: if the refreshed token still
  // comes back 401 (e.g. the account was deactivated server-side), we must
  // not keep calling tryRefreshToken() forever — retry exactly once.
  if (response.status === 401 && auth && !isRetry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return request<T>(path, options, true);
    }
    await clearAuthTokens();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function tryRefreshToken(): Promise<boolean> {
  const tokens = await getAuthTokens();
  if (!tokens?.refreshToken) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    });
    if (!response.ok) return false;
    const body = await response.json();
    await setAuthTokens({ accessToken: body.access_token, refreshToken: body.refresh_token });
    return true;
  } catch {
    return false;
  }
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "DELETE" }),
  blob: async (path: string, options: RequestOptions = {}, isRetry = false): Promise<Blob> => {
    const { auth = true, headers, ...rest } = options;
    const finalHeaders = new Headers(headers);

    if (auth) {
      const tokens = await getAuthTokens();
      if (tokens?.accessToken) finalHeaders.set("Authorization", `Bearer ${tokens.accessToken}`);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, { ...rest, headers: finalHeaders });

    if (response.status === 401 && auth && !isRetry) {
      const refreshed = await tryRefreshToken();
      if (refreshed) return apiClient.blob(path, options, true);
      await clearAuthTokens();
    }

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new ApiError(response.status, body.detail ?? "Request failed");
    }

    return response.blob();
  },
};
