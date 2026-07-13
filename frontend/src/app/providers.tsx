"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { logout as apiLogout, restoreSession } from "@/lib/api";
import type { CurrentUser } from "@/lib/types";

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
    () => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } }),
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
      <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    </QueryClientProvider>
  );
}
