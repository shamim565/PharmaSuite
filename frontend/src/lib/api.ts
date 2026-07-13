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
};

async function rawFetch(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
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
  patch: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};

export async function login(identifier: string, password: string) {
  const data = await apiFetch<{ access: string; user: import("./types").CurrentUser }>("/auth/login/", {
    method: "POST",
    body: { identifier, password },
    auth: false,
  });
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
