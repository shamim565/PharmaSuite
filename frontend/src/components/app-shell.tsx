"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  ArrowRightLeft,
  Banknote,
  BarChart3,
  Bell,
  Boxes,
  BriefcaseBusiness,
  Calculator,
  ClipboardList,
  Coins,
  Ellipsis,
  Home,
  Hourglass,
  KeyRound,
  Landmark,
  Layers,
  LayoutDashboard,
  Library,
  Menu,
  PackageCheck,
  Pill,
  PlusCircle,
  ReceiptText,
  Scale,
  ScrollText,
  Settings,
  ShieldCheck,
  Stethoscope,
  Target,
  Truck,
  Undo2,
  UserCog,
  UsersRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/app/providers";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { useDebouncedValue } from "@/lib/hooks";
import type { NotificationList, SearchResults } from "@/lib/types";

type NavItem = {
  href: string;
  label: string;
  permission: string;
  altPermission?: string;
  icon: LucideIcon;
  /**
   * Explicit slot rank for the mobile bottom nav. The four visible items with
   * the lowest rank are shown — never derived from array position, so roles
   * with different permission sets still get a sensible bottom bar.
   */
  mobileRank?: number;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", permission: "DASHBOARD_VIEW", icon: LayoutDashboard, mobileRank: 1 },
  { href: "/sales", label: "Sales", permission: "SALE_VIEW", icon: ReceiptText, mobileRank: 2 },
  { href: "/dues", label: "Dues", permission: "PAYMENT_VIEW", icon: Hourglass, mobileRank: 3 },
  { href: "/payments", label: "Payments", permission: "PAYMENT_VIEW", icon: Banknote, mobileRank: 4 },
  { href: "/returns", label: "Returns", permission: "SRET_VIEW", icon: Undo2 },
  { href: "/adjustments", label: "Adjustments", permission: "STOCK_VIEW", icon: Scale },
  { href: "/purchases", label: "Purchases", permission: "PURCHASE_VIEW", icon: ArrowLeftRight, mobileRank: 6 },
  {
    href: "/purchases/orders",
    label: "Purchase Orders",
    permission: "PURCHASE_VIEW",
    icon: ClipboardList,
  },
  {
    href: "/deliveries",
    label: "Deliveries",
    permission: "SALE_VIEW",
    icon: PackageCheck,
  },
  { href: "/inventory", label: "Inventory", permission: "STOCK_VIEW", icon: Boxes, mobileRank: 5 },
  { href: "/transfers", label: "Transfers", permission: "STOCK_TRANSFER", icon: ArrowRightLeft },
  { href: "/items", label: "Items", permission: "MEDICINE_VIEW", icon: Pill },
  { href: "/batches", label: "Batches", permission: "STOCK_VIEW", icon: Layers },
  { href: "/customers", label: "Customers", permission: "CUSTOMER_VIEW", icon: UsersRound, mobileRank: 7 },
  { href: "/doctors", label: "Doctors", permission: "DOCTOR_VIEW", icon: Stethoscope, mobileRank: 9 },
  { href: "/reps", label: "Reps", permission: "REP_VIEW", icon: BriefcaseBusiness, mobileRank: 8 },
  {
    href: "/targets",
    label: "Targets",
    permission: "REP_VIEW",
    icon: Target,
  },
  { href: "/suppliers", label: "Suppliers", permission: "SUPPLIER_VIEW", icon: Truck },
  { href: "/accounts", label: "Accounts", permission: "ACCOUNT_VIEW", icon: Landmark },
  { href: "/expenses", label: "Expenses", permission: "EXPENSE_VIEW", icon: Calculator },
  { href: "/income", label: "Income", permission: "INCOME_VIEW", icon: PlusCircle },
  { href: "/reports", label: "Reports", permission: "REPORT_VIEW", icon: BarChart3 },
  { href: "/catalog", label: "Catalog", permission: "MEDICINE_MANAGE", icon: Library },
  { href: "/users", label: "Users", permission: "USER_VIEW", icon: UserCog },
  {
    href: "/roles",
    label: "Roles",
    permission: "ROLE_VIEW",
    altPermission: "ROLE_MANAGE",
    icon: KeyRound,
  },
  { href: "/branches", label: "Branches", permission: "BRANCH_VIEW", icon: Home },
  { href: "/audit", label: "Audit", permission: "AUDIT_VIEW", icon: ScrollText },
  { href: "/cheques", label: "Cheques", permission: "CHEQUE_VIEW", icon: Coins },
  { href: "/settings", label: "Settings", permission: "SETTINGS_VIEW", icon: Settings },
  { href: "/security", label: "Security", permission: "", icon: ShieldCheck },
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
        className="relative rounded-lg px-2 py-1 text-slate-600 hover:bg-slate-100"
      >
        <Bell aria-hidden size={18} />
        {(unreadQuery.data?.count ?? 0) > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger-600 px-1 text-[10px] font-bold text-white">
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
              <Link
                href="/notifications"
                onClick={() => setOpen(false)}
                className="text-xs text-primary-700 hover:underline"
              >
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
                      {item.body ? (
                        <p className="truncate text-xs text-slate-500">{item.body}</p>
                      ) : null}
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

function GlobalSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const debouncedQ = useDebouncedValue(q);

  const searchQuery = useQuery({
    queryKey: ["search", debouncedQ],
    queryFn: () => api.get<SearchResults>(`/search/?q=${encodeURIComponent(debouncedQ)}`),
    enabled: debouncedQ.trim().length >= 2,
  });

  const sections: Array<{
    key: keyof SearchResults["results"];
    label: string;
    fields: string[];
    href: string;
    hrefFor?: (row: { id: string }) => string;
  }> = [
    { key: "medicines", label: "Medicines", fields: ["code", "name"], href: "/inventory" },
    { key: "customers", label: "Customers", fields: ["code", "name", "phone"], href: "/customers" },
    { key: "suppliers", label: "Suppliers", fields: ["code", "name", "phone"], href: "/suppliers" },
    { key: "doctors", label: "Doctors", fields: ["code", "name"], href: "/doctors" },
    {
      key: "invoices",
      label: "Invoices",
      fields: ["number", "customer__name"],
      href: "/sales",
      hrefFor: (row) => `/sales/${row.id}`,
    },
    {
      key: "purchases",
      label: "Purchases",
      fields: ["number", "supplier__name"],
      href: "/purchases",
      hrefFor: (row) => `/purchases/${row.id}`,
    },
  ];

  type FlatRow = { key: string; sectionKey: string; label: string; href: string };

  const flat: FlatRow[] = [];
  for (const section of sections) {
    for (const row of searchQuery.data?.results[section.key] ?? []) {
      flat.push({
        key: `${section.key}-${row.id}`,
        sectionKey: section.key,
        label: section.fields
          .map((field) => row[field as keyof typeof row] ?? "")
          .filter(Boolean)
          .join(" · "),
        href: section.hrefFor ? section.hrefFor(row) : section.href,
      });
    }
  }

  useEffect(() => {
    setHighlight(0);
  }, [debouncedQ, searchQuery.data]);

  const hasAny = flat.length > 0;
  const openMenu = (target: FlatRow) => {
    setOpen(false);
    setQ("");
    router.push(target.href);
  };

  return (
    <div className="relative w-72">
      <input
        value={q}
        aria-label="Global search"
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setHighlight((value) => Math.min(value + 1, Math.max(flat.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlight((value) => Math.max(value - 1, 0));
          } else if (e.key === "Enter") {
            const target = flat[highlight];
            if (target) {
              e.preventDefault();
              openMenu(target);
            }
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        placeholder="Search medicines, customers, invoices…"
        className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm outline-none focus:border-primary-500 focus:bg-white"
      />
      {open && q.trim().length >= 2 ? (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute left-0 right-0 z-40 mt-1 max-h-96 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
            {searchQuery.isFetching && !hasAny ? (
              <p className="p-3 text-sm text-slate-500">Searching…</p>
            ) : null}
            {!hasAny && !searchQuery.isFetching ? (
              <p className="p-3 text-sm text-slate-500">No results.</p>
            ) : null}
            {sections.map((section) => {
              const rows = flat.filter((row) => row.sectionKey === section.key);
              if (!rows.length) return null;
              return (
                <div key={section.key} className="border-b border-slate-100 last:border-0">
                  <p className="px-3 pt-2 text-xs font-bold uppercase tracking-wide text-slate-500">
                    {section.label}
                  </p>
                  {rows.map((row) => {
                    const index = flat.indexOf(row);
                    return (
                      <button
                        key={row.key}
                        onMouseEnter={() => setHighlight(index)}
                        className={`w-full px-3 py-1.5 text-left text-sm ${
                          index === highlight ? "bg-primary-50" : "hover:bg-slate-50"
                        }`}
                        onClick={() => openMenu(row)}
                      >
                        {row.label}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}

function BranchSwitcher({ compact = false }: { compact?: boolean }) {
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();
  const branchesQuery = useQuery({
    queryKey: ["branches", "switcher"],
    queryFn: () =>
      api.get<{ count: number; results: Array<{ id: string; name: string }> }>(
        "/branches/?page_size=200",
      ),
    enabled: Boolean(user),
  });
  const switchMutation = useMutation({
    meta: { successMessage: "Branch switched" },
    mutationFn: (id: string) =>
      api.patch<{ default_branch_id: string }>("/auth/me/", { default_branch_id: id }),
    onSuccess: (data) => {
      if (user) setUser({ ...user, default_branch_id: data.default_branch_id });
      queryClient.invalidateQueries();
    },
  });

  if (!user || !branchesQuery.data) return null;
  return (
    <select
      aria-label="Switch branch"
      value={user.default_branch_id ?? ""}
      onChange={(e) => switchMutation.mutate(e.target.value)}
      className={`rounded-lg border border-slate-200 bg-slate-50 text-slate-700 outline-none focus:border-primary-500 ${
        compact ? "max-w-[8.5rem] truncate px-1.5 py-1 text-xs" : "px-2 py-1.5 text-sm"
      }`}
    >
      {branchesQuery.data.results.map((branch) => (
        <option key={branch.id} value={branch.id}>
          {branch.name}
        </option>
      ))}
    </select>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, signOut, hasPerm } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const items = NAV_ITEMS.filter(
    (item) =>
      !item.permission ||
      hasPerm(item.permission) ||
      (item.altPermission ? hasPerm(item.altPermission) : false),
  );

  /**
   * Mobile bottom nav slots are explicitly configured via mobileRank:
   * take the four visible, ranked items (lowest rank first), falling back to
   * NAV_ITEMS order for unranked items if fewer than four are ranked.
   */
  const mobileItems = (() => {
    const visible = items;
    const ranked = visible
      .filter((item) => item.mobileRank !== undefined)
      .sort((a, b) => (a.mobileRank ?? 0) - (b.mobileRank ?? 0));
    if (ranked.length >= 4) return ranked.slice(0, 4);
    const picked = new Set(ranked.map((item) => item.href));
    return [...ranked, ...visible.filter((item) => !picked.has(item.href))].slice(0, 4);
  })();

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  const nav = (
    <nav className="space-y-1">
      {items.map((item) => {
        const active =
          pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setDrawerOpen(false)}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
              active ? "bg-primary-50 text-primary-700" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <item.icon aria-hidden size={18} className="shrink-0" />
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
          <p className="text-sm font-bold text-primary-700">PharmaSuite</p>
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
      <header className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2.5 lg:hidden">
        <button
          aria-label="Open menu"
          onClick={() => setDrawerOpen(true)}
          className="rounded-lg px-2.5 py-2 text-slate-600 hover:bg-slate-100"
        >
          <Menu aria-hidden size={22} />
        </button>
        <p className="min-w-0 flex-1 truncate text-sm font-bold text-primary-700">PharmaSuite</p>
        <BranchSwitcher compact />
        <NotificationBell />
      </header>

      {/* Mobile drawer */}
      {drawerOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between p-4 pb-2">
              <p className="text-sm font-bold text-primary-700">Menu</p>
              <button
                aria-label="Close menu"
                className="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-100"
                onClick={() => setDrawerOpen(false)}
              >
                <X aria-hidden size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-4 pb-4">
              {nav}
              <div className="mt-4 border-t border-slate-100 pt-4">
                <Button variant="secondary" size="sm" className="w-full" onClick={handleSignOut}>
                  Sign out
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex-1">
        {/* Desktop topbar */}
        <div className="hidden items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3 lg:flex">
          <p className="text-sm text-slate-500">
            Branch:{" "}
            <span className="font-medium text-slate-700">
              {user?.branches.find((b) => b.id === user.default_branch_id)?.name ??
                user?.branches[0]?.name ??
                "—"}
            </span>
          </p>
          <GlobalSearch />
          <div className="flex items-center gap-3">
            <BranchSwitcher />
            <p className="text-sm text-slate-600">
              Signed in as <span className="font-medium">{user?.full_name}</span>
            </p>
            <NotificationBell />
          </div>
        </div>

        <main className="mx-auto w-full max-w-6xl p-4 pb-20 lg:p-6">{children}</main>

        {/* Mobile bottom nav */}
        <nav
          className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-slate-200 bg-white lg:hidden"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          {mobileItems.map((item) => {
            const active =
              pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex min-h-[3.75rem] flex-col items-center justify-center gap-0.5 text-[11px] ${
                  active ? "text-primary-700" : "text-slate-500"
                }`}
              >
                <item.icon aria-hidden size={20} />
                {item.label}
              </Link>
            );
          })}
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open full menu"
            className={`flex min-h-[3.75rem] flex-col items-center justify-center gap-0.5 text-[11px] ${
              drawerOpen ? "text-primary-700" : "text-slate-500"
            }`}
          >
            <Ellipsis aria-hidden size={20} />
            More
          </button>
        </nav>
      </div>
    </div>
  );
}
