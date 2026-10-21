"use client";

import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ToastProvider, pushToast } from "@/components/ui";
import { ApiError, logout as apiLogout, restoreSession, setUnauthorizedHandler } from "@/lib/api";
import type { CurrentUser } from "@/lib/types";

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: {
      /** Toast shown after this mutation succeeds. A function receives the mutation variables/data. */
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      successMessage?: string | ((variables: any, data: any) => string);
    };
  }
}

type AuthState = {
  user: CurrentUser | null;
  loading: boolean;
  setUser: (user: CurrentUser | null) => void;
  signOut: () => Promise<void>;
  hasPerm: (code: string) => boolean;
};

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  setUser: () => undefined,
  signOut: async () => undefined,
  hasPerm: () => false,
});

export function useAuth() {
  return useContext(AuthContext);
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        mutationCache: new MutationCache({
          onError: (error) => {
            // Field-level validation errors are already shown inline on the
            // form — only toast errors the user cannot see elsewhere.
            if (error instanceof ApiError && error.fieldErrors) return;
            pushToast(error instanceof ApiError ? error.message : "Something went wrong", "error");
          },
          onSuccess: (data, variables, _context, mutation) => {
            const meta = mutation.meta?.successMessage;
            const message = typeof meta === "function" ? meta(variables, data) : meta;
            if (message) pushToast(message, "success");
          },
        }),
        defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
      }),
  );
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    restoreSession()
      .then((restored) => {
        if (mounted) setUser(restored);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      pushToast("Session expired — please sign in again.", "error");
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const hasPerm = useCallback(
    (code: string) => Boolean(user && (user.is_superuser || user.permissions.includes(code))),
    [user],
  );

  const value = useMemo(
    () => ({ user, loading, setUser, signOut, hasPerm }),
    [user, loading, setUser, signOut, hasPerm],
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={value}>
        <ToastProvider>{children}</ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>
  );
}
