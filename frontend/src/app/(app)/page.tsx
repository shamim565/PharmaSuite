"use client";

import { useQuery } from "@tanstack/react-query";

import { Card, CardHeader, ErrorBanner, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/types";

function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
      {hint ? <p className="text-xs text-slate-400">{hint}</p> : null}
    </Card>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary/"),
  });

  if (isLoading) return <Spinner label="Loading dashboard…" />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-slate-800">Dashboard</h1>
        {data ? (
          <span className="text-xs text-slate-500">
            {data.branch_scope === "ALL" ? "All branches" : "Assigned branches"} ·{" "}
            {new Date(data.generated_at).toLocaleString()}
          </span>
        ) : null}
      </div>

      <ErrorBanner error={error} />

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard
              label="Medicines"
              value={String(data.medicines.active)}
              hint={`${data.medicines.total} total`}
            />
            <KpiCard
              label="Users"
              value={String(data.users.active)}
              hint={`${data.users.total} total`}
            />
            <KpiCard
              label="Branches"
              value={String(data.branches.active)}
              hint={`${data.branches.total} total`}
            />
            <KpiCard label="Roles" value={String(data.roles.total)} hint="RBAC roles" />
          </div>

          <Card>
            <CardHeader
              title="Operations"
              subtitle="Business KPIs unlock as the sales, inventory and finance sprints land."
            />
            <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
              {[
                ["Sales today", data.operations.sales_today],
                ["Collections today", data.operations.collections_today],
                ["Customer due", data.operations.customer_due],
                ["Supplier payable", data.operations.supplier_payable],
                ["Cash position", data.operations.cash_position],
                ["Stock value", data.operations.stock_value],
                ["Low stock", data.operations.low_stock_count],
                ["Near expiry", data.operations.near_expiry_count],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className="text-lg font-semibold text-slate-400">
                    {value === null ? "—" : String(value)}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}
