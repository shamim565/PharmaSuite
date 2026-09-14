const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  fieldErrors: Record<string, string[]> | null;
  requestId: string | null;

  constructor(
    message: string,
    code: string,
    status: number,
    fieldErrors: Record<string, string[]> | null = null,
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.requestId = requestId;
  }
}

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

let unauthorizedHandler: (() => void) | null = null;
let lastUnauthorizedNotify = 0;

/**
 * Register a callback invoked when the session can no longer be refreshed
 * (expired/revoked). The app uses this to clear auth state and redirect to
 * the login screen instead of stranding the user on 401 error banners.
 */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

function notifyUnauthorized() {
  accessToken = null;
  const now = Date.now();
  // De-duplicate: several parallel requests will all 401 at once.
  if (now - lastUnauthorizedNotify < 5_000) return;
  lastUnauthorizedNotify = now;
  unauthorizedHandler?.();
}

export const authToken = {
  get: () => accessToken,
  set: (token: string | null) => {
    accessToken = token;
  },
};

async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_URL}/auth/refresh/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = (await res.json()) as { access: string };
        accessToken = data.access;
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  auth?: boolean;
  headers?: Record<string, string>;
};

async function rawFetch(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.auth !== false && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  return fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    credentials: "include",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await rawFetch(path, options);

  if (response.status === 401 && options.auth !== false) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await rawFetch(path, options);
    }
    if (response.status === 401) notifyUnauthorized();
  }

  if (!response.ok) {
    let code = String(response.status);
    let message = "Request failed";
    let fieldErrors: Record<string, string[]> | null = null;
    let requestId: string | null = null;
    try {
      const body = await response.json();
      code = body.code ?? code;
      message = body.message ?? message;
      fieldErrors = body.field_errors ?? null;
      requestId = body.request_id ?? null;
    } catch {
      // keep defaults
    }
    throw new ApiError(message, code, response.status, fieldErrors, requestId);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  postWithKey: <T>(path: string, body: unknown, key: string) =>
    apiFetch<T>(path, { method: "POST", body, headers: { "Idempotency-Key": key } }),
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};

export async function apiUpload(
  path: string,
  file: File,
  fields?: Record<string, string>,
): Promise<unknown> {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields ?? {})) {
    form.append(key, value);
  }
  let response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    body: form,
  });
  if (response.status === 401) {
    if (await tryRefresh()) {
      response = await fetch(`${API_URL}${path}`, {
        method: "POST",
        credentials: "include",
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        body: form,
      });
    }
    if (response.status === 401) notifyUnauthorized();
  }
  if (!response.ok) {
    let message = "Upload failed";
    try {
      const body = await response.json();
      message = body.message ?? message;
    } catch {
      // keep default
    }
    throw new ApiError(message, String(response.status), response.status);
  }
  return response.json();
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  let response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (response.status === 401) {
    if (await tryRefresh()) {
      response = await fetch(`${API_URL}${path}`, {
        credentials: "include",
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      });
    }
    if (response.status === 401) notifyUnauthorized();
  }
  if (!response.ok) {
    throw new ApiError("Download failed", String(response.status), response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export type LoginResult =
  | { mfa_required: true; mfa_token: string }
  | { mfa_required: false; user: import("./types").CurrentUser };

export async function login(identifier: string, password: string): Promise<LoginResult> {
  const data = await apiFetch<{
    mfa_required?: boolean;
    mfa_token?: string;
    access?: string;
    user?: import("./types").CurrentUser;
  }>("/auth/login/", {
    method: "POST",
    body: { identifier, password },
    auth: false,
  });
  if (data.mfa_required) {
    return { mfa_required: true, mfa_token: data.mfa_token ?? "" };
  }
  accessToken = data.access ?? null;
  return { mfa_required: false, user: data.user as import("./types").CurrentUser };
}

export async function loginMfa(mfaToken: string, code: string) {
  const data = await apiFetch<{ access: string; user: import("./types").CurrentUser }>(
    "/auth/login/mfa/",
    {
      method: "POST",
      body: { mfa_token: mfaToken, code },
      auth: false,
    },
  );
  accessToken = data.access;
  return data.user;
}

export async function logout() {
  try {
    await apiFetch("/auth/logout/", { method: "POST", auth: false });
  } finally {
    accessToken = null;
  }
}

export async function restoreSession() {
  const refreshed = await tryRefresh();
  if (!refreshed) return null;
  try {
    return await apiFetch<import("./types").CurrentUser>("/auth/me/");
  } catch {
    accessToken = null;
    return null;
  }
}
