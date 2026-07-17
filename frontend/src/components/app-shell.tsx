"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/app/providers";
import { Button } from "@/components/ui";

type NavItem = { href: string; label: string; permission: string; icon: string };

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", permission: "DASHBOARD_VIEW", icon: "▦" },
  { href: "/sales", label: "Sales", permission: "SALE_VIEW", icon: "🧾" },
  { href: "/purchases", label: "Purchases", permission: "PURCHASE_VIEW", icon: "⇄" },
  { href: "/inventory", label: "Inventory", permission: "STOCK_VIEW", icon: "▣" },
  { href: "/items", label: "Items", permission: "MEDICINE_VIEW", icon: "℞" },
  { href: "/batches", label: "Batches", permission: "STOCK_VIEW", icon: "◫" },
  { href: "/customers", label: "Customers", permission: "CUSTOMER_VIEW", icon: "☺" },
  { href: "/suppliers", label: "Suppliers", permission: "SUPPLIER_VIEW", icon: "⛟" },
  { href: "/catalog", label: "Catalog", permission: "MEDICINE_MANAGE", icon: "▤" },
  { href: "/users", label: "Users", permission: "USER_VIEW", icon: "👤" },
  { href: "/branches", label: "Branches", permission: "BRANCH_VIEW", icon: "⌂" },
];

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
        <span className="text-xs text-slate-500">{user?.full_name?.split(" ")[0]}</span>
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
          <div className="text-sm text-slate-600">
            Signed in as <span className="font-medium">{user?.full_name}</span>
          </div>
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
