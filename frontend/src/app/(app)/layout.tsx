"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/app/providers";
import { AppShell } from "@/components/app-shell";
import { Spinner } from "@/components/ui";

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="p-10">
        <Spinner label="Restoring session…" />
      </div>
    );
  }
  if (!user) return null;

  return <AppShell>{children}</AppShell>;
}
