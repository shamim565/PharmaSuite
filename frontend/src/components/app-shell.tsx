"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { NotificationList } from "@/lib/types";

type NavItem = { href: string; label: string; permission: string; icon: string };

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", permission: "DASHBOARD_VIEW", icon: "▦" },
  { href: "/sales", label: "Sales", permission: "SALE_VIEW", icon: "🧾" },
  { href: "/dues", label: "Dues", permission: "PAYMENT_VIEW", icon: "⏳" },
  { href: "/payments", label: "Payments", permission: "PAYMENT_VIEW", icon: "💵" },
  { href: "/returns", label: "Returns", permission: "SRET_VIEW", icon: "↩" },
  { href: "/adjustments", label: "Adjustments", permission: "STOCK_VIEW", icon: "⚖" },
  { href: "/purchases", label: "Purchases", permission: "PURCHASE_VIEW", icon: "⇄" },
  { href: "/inventory", label: "Inventory", permission: "STOCK_VIEW", icon: "▣" },
  { href: "/items", label: "Items", permission: "MEDICINE_VIEW", icon: "℞" },
  { href: "/batches", label: "Batches", permission: "STOCK_VIEW", icon: "◫" },
  { href: "/customers", label: "Customers", permission: "CUSTOMER_VIEW", icon: "☺" },
  { href: "/doctors", label: "Doctors", permission: "DOCTOR_VIEW", icon: "🩺" },
  { href: "/reps", label: "Reps", permission: "REP_VIEW", icon: "🧑‍💼" },
  { href: "/suppliers", label: "Suppliers", permission: "SUPPLIER_VIEW", icon: "⛟" },
  { href: "/accounts", label: "Accounts", permission: "ACCOUNT_VIEW", icon: "🏦" },
  { href: "/expenses", label: "Expenses", permission: "EXPENSE_VIEW", icon: "🧮" },
  { href: "/income", label: "Income", permission: "INCOME_VIEW", icon: "➕" },
  { href: "/reports", label: "Reports", permission: "REPORT_VIEW", icon: "📊" },
  { href: "/catalog", label: "Catalog", permission: "MEDICINE_MANAGE", icon: "▤" },
  { href: "/users", label: "Users", permission: "USER_VIEW", icon: "👤" },
  { href: "/branches", label: "Branches", permission: "BRANCH_VIEW", icon: "⌂" },
  { href: "/audit", label: "Audit", permission: "AUDIT_VIEW", icon: "📜" },
  { href: "/settings", label: "Settings", permission: "SETTINGS_VIEW", icon: "⚙" },
];

function NotificationBell() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const unreadQuery = useQuery({
    queryKey: ["unread-count"],
    queryFn: () => api.get<{ count: number }>("/notifications/unread-count/"),
    refetchInterval: 60_000,
    enabled: Boolean(user),
  });
  const listQuery = useQuery({
    queryKey: ["notifications", "latest"],
    queryFn: () => api.get<NotificationList>("/notifications/?page_size=8"),
    enabled: open && Boolean(user),
  });

  const readMutation = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["unread-count"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const openItem = (item: { id: string; deep_link: string }) => {
    readMutation.mutate(item.id);
    setOpen(false);
    if (item.deep_link) router.push(item.deep_link);
  };

  return (
    <div className="relative">
      <button
        aria-label="Notifications"
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-lg px-2 py-1 text-lg text-slate-600 hover:bg-slate-100"
      >
        🔔
        {(unreadQuery.data?.count ?? 0) > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">
            {Math.min(unreadQuery.data?.count ?? 0, 9)}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-1 w-80 rounded-xl border border-slate-200 bg-white shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
              <p className="text-sm font-semibold text-slate-700">Notifications</p>
              <Link href="/notifications" onClick={() => setOpen(false)} className="text-xs text-emerald-700 hover:underline">
                View all
              </Link>
            </div>
            {listQuery.data?.results.length ? (
              <ul className="max-h-80 divide-y divide-slate-100 overflow-auto">
                {listQuery.data.results.map((item) => (
                  <li key={item.id}>
                    <button
                      className={`w-full px-3 py-2 text-left hover:bg-slate-50 ${item.is_read ? "opacity-60" : ""}`}
                      onClick={() => openItem(item)}
                    >
                      <p className="text-sm font-medium">{item.title}</p>
                      {item.body ? <p className="truncate text-xs text-slate-500">{item.body}</p> : null}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-4 text-sm text-slate-500">Nothing here yet.</p>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, signOut, hasPerm } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const items = NAV_ITEMS.filter((item) => hasPerm(item.permission));

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  const nav = (
    <nav className="space-y-1">
      {items.map((item) => {
        const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setDrawerOpen(false)}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
              active ? "bg-emerald-50 text-emerald-700" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <span aria-hidden className="text-base">
              {item.icon}
            </span>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen lg:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-slate-200 bg-white p-4 lg:block">
        <div className="mb-6 px-2">
          <p className="text-sm font-bold text-emerald-700">Medicine Dealer ERP</p>
          <p className="text-xs text-slate-500">{user?.roles[0]?.name ?? "—"}</p>
        </div>
        {nav}
        <div className="mt-6 border-t border-slate-100 pt-4">
          <Button variant="secondary" size="sm" className="w-full" onClick={handleSignOut}>
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <button
          aria-label="Open menu"
          onClick={() => setDrawerOpen(true)}
          className="rounded-lg px-2 py-1 text-xl text-slate-600 hover:bg-slate-100"
        >
          ☰
        </button>
        <p className="text-sm font-bold text-emerald-700">Medicine Dealer ERP</p>
        <div className="flex items-center gap-1">
          <NotificationBell />
          <span className="text-xs text-slate-500">{user?.full_name?.split(" ")[0]}</span>
        </div>
      </header>

      {/* Mobile drawer */}
      {drawerOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64 space-y-4 bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between">
              <p className="text-sm font-bold text-emerald-700">Menu</p>
              <button
                aria-label="Close menu"
                className="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-100"
                onClick={() => setDrawerOpen(false)}
              >
                ✕
              </button>
            </div>
            {nav}
            <Button variant="secondary" size="sm" className="w-full" onClick={handleSignOut}>
              Sign out
            </Button>
          </div>
        </div>
      ) : null}

      <div className="flex-1">
        {/* Desktop topbar */}
        <div className="hidden items-center justify-between border-b border-slate-200 bg-white px-6 py-3 lg:flex">
          <p className="text-sm text-slate-500">
            Branch:{" "}
            <span className="font-medium text-slate-700">
              {user?.branches.find((b) => b.id === user.default_branch_id)?.name ??
                user?.branches[0]?.name ??
                "—"}
            </span>
          </p>
          <p className="text-sm text-slate-600">
            Signed in as <span className="font-medium">{user?.full_name}</span>
          </p>
          <NotificationBell />
        </div>

        <main className="mx-auto w-full max-w-6xl p-4 pb-20 lg:p-6">{children}</main>

        {/* Mobile bottom nav */}
        <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t border-slate-200 bg-white lg:hidden">
          {items.slice(0, 4).map((item) => {
            const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center gap-0.5 py-2 text-[11px] ${
                  active ? "text-emerald-700" : "text-slate-500"
                }`}
              >
                <span aria-hidden className="text-lg">
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
